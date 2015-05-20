import os
import sys
import base64
import time
import datetime
import collections
import h5py
import re
from twisted.internet import reactor

## Data types for variable defintions

Independent = collections.namedtuple('Independent', ['label', 'shape', 'datatype', 'unit'])
Dependent = collections.namedtuple('Dependent', ['label', 'legend', 'shape', 'datatype', 'unit'])

try:
    import numpy as np
    use_numpy = True
except ImportError, e:
    print e
    print "Numpy not imported.  The DataVault will operate, but will be slower."
    use_numpy = False
from labrad import types as T
from . import errors, util

TIME_FORMAT = '%Y-%m-%d, %H:%M:%S'
PRECISION = 12 # digits of precision to use when saving data
DATA_FORMAT = '%%.%dG' % PRECISION
FILE_TIMEOUT = 60 # how long to keep datafiles open if not accessed
DATA_TIMEOUT = 300 # how long to keep data in memory if not accessed
DATA_URL_PREFIX = 'data:application/labrad;base64,'

def time_to_str(t):
    return t.strftime(TIME_FORMAT)

def time_from_str(s):
    return datetime.datetime.strptime(s, TIME_FORMAT)

def labrad_urlencode(data):
    data_bytes, t = T.flatten(data)
    all_bytes, _ = T.flatten((str(t), data_bytes), 'ss')
    data_url = DATA_URL_PREFIX + base64.urlsafe_b64encode(all_bytes)
    return data_url

def labrad_urldecode(data_url):
    if data_url.startswith(DATA_URL_PREFIX):
        # decode parameter data from dataurl
        all_bytes = base64.urlsafe_b64decode(data_url[len(DATA_URL_PREFIX):])
        t, data_bytes = T.unflatten(all_bytes, 'ss')
        data = T.unflatten(data_bytes, t)
        return data
    else:
        raise ValueError("Trying to labrad_urldecode data that doesn't start with prefix: " % (DATA_URL_PREFIX,))

class SelfClosingFile(object):
    """
    A container for a file object that closes the underlying file handle if not
    accessed within a specified timeout. Call this container to get the file handle.
    """
    def __init__(self, opener=open, open_args=(), open_kw={}, timeout=FILE_TIMEOUT, touch=True):
        self.opener = opener
        self.open_args = open_args
        self.open_kw = open_kw
        self.timeout = timeout
        self.callbacks = []
        if touch:
            self.__call__()

    def __call__(self):
        if not hasattr(self, '_file'):
            self._file = self.opener(*self.open_args, **self.open_kw)
            self._fileTimeoutCall = reactor.callLater(self.timeout, self._fileTimeout)
        else:
            self._fileTimeoutCall.reset(self.timeout)
        return self._file

    def _fileTimeout(self):
        for callback in self.callbacks:
            callback(self)
        self._file.close()
        del self._file
        del self._fileTimeoutCall

    def size(self):
        return os.fstat(self().fileno()).st_size

    def onClose(self, callback):
        self.callbacks.append(callback)

class IniData(object):
    """
    Handles dataset metadata stored in INI files.  

    This is used via subclassing mostly out of laziness: this was the
    easy way to separate it from the code that messes with the acutal
    data storage so that the data storage can be modified to use HDF5
    and complex data structures.  Once the HDF5 stuff is finished,
    this can be changed to use composition rather than inheritance.
    This provides the load() and save() methods to read and write the
    INI file as well as accessors for all the metadata attributes.
    """
    def load(self):
        S = util.DVSafeConfigParser()
        S.read(self.infofile)

        gen = 'General'
        self.title = S.get(gen, 'Title', raw=True)
        self.created = time_from_str(S.get(gen, 'Created'))
        self.accessed = time_from_str(S.get(gen, 'Accessed'))
        self.modified = time_from_str(S.get(gen, 'Modified'))

        def getInd(i):
            sec = 'Independent %d' % (i+1)
            label = S.get(sec, 'Label', raw=True)
            units = S.get(sec, 'Units', raw=True)
            return Independent(label=label, shape=(1,), datatype='v', unit=units)
        count = S.getint(gen, 'Independent')
        self.independents = [getInd(i) for i in range(count)]

        def getDep(i):
            sec = 'Dependent %d' % (i+1)
            label = S.get(sec, 'Label', raw=True)
            units = S.get(sec, 'Units', raw=True)
            categ = S.get(sec, 'Category', raw=True)
            return Dependent(label=categ, legend=label, shape=(1,), datatype='v', unit=units)
        count = S.getint(gen, 'Dependent')
        self.dependents = [getDep(i) for i in range(count)]
        
        self.cols = len(self.independents + self.dependents)

        def getPar(i):
            sec = 'Parameter %d' % (i+1)
            label = S.get(sec, 'Label', raw=True)
            raw = S.get(sec, 'Data', raw=True)
            if raw.startswith(DATA_URL_PREFIX):
                # decode parameter data from dataurl
                data = labrad_urldecode(raw)
            else:
                # old parameters may have been saved using repr
                data = T.evalLRData(raw)
            return dict(label=label, data=data)
        count = S.getint(gen, 'Parameters')
        self.parameters = [getPar(i) for i in range(count)]

        # get comments if they're there
        if S.has_section('Comments'):
            def getComment(i):
                sec = 'Comments'
                time, user, comment = eval(S.get(sec, 'c%d' % i, raw=True))
                return time_from_str(time), user, comment
            count = S.getint(gen, 'Comments')
            self.comments = [getComment(i) for i in range(count)]
        else:
            self.comments = []

    def save(self):
        S = util.DVSafeConfigParser()

        sec = 'General'
        S.add_section(sec)
        S.set(sec, 'Created',  time_to_str(self.created))
        S.set(sec, 'Accessed', time_to_str(self.accessed))
        S.set(sec, 'Modified', time_to_str(self.modified))
        S.set(sec, 'Title',       self.title)
        S.set(sec, 'Independent', repr(len(self.independents)))
        S.set(sec, 'Dependent',   repr(len(self.dependents)))
        S.set(sec, 'Parameters',  repr(len(self.parameters)))
        S.set(sec, 'Comments',    repr(len(self.comments)))

        for i, ind in enumerate(self.independents):
            sec = 'Independent %d' % (i+1)
            S.add_section(sec)
            S.set(sec, 'Label', ind.label)
            S.set(sec, 'Units', ind.units)

        for i, dep in enumerate(self.dependents):
            sec = 'Dependent %d' % (i+1)
            S.add_section(sec)
            S.set(sec, 'Label',    dep.legend)
            S.set(sec, 'Units',    dep.unit)
            S.set(sec, 'Category', dep.label)

        for i, par in enumerate(self.parameters):
            sec = 'Parameter %d' % (i+1)
            S.add_section(sec)
            S.set(sec, 'Label', par['label'])
            # encode the parameter value as a data-url
            data_url = labrad_urlencode(par['data'])
            S.set(sec, 'Data', data_url)

        sec = 'Comments'
        S.add_section(sec)
        for i, (time, user, comment) in enumerate(self.comments):
            time = time_to_str(time)
            S.set(sec, 'c%d' % i, repr((time, user, comment)))

        with open(self.infofile, 'w') as f:
            S.write(f)

    def initialize_info(self, title, indep, dep):
        self.title = title
        self.accessed = self.modified = self.created = datetime.datetime.now()
        self.independents = indep
        self.dependents = dep
        self.parameters = []
        self.comments = []
        self.cols = len(indep) + len(dep)

    def access(self):
        self.accessed = datetime.datetime.now()

    def getIndependents(self):
        return self.independents

    def getDependents(self):
        return self.dependents

    def getRowType(self):
        units = []
        for var in self.independents+self.dependents:
            units.append("v[%s]"%var.unit)
        type_tag = '*(' + (','.join(units)) + ')'
        return type_tag

    def getTransposeType(self):
        units = []
        for var in self.independents+self.dependents:
            units.append('*v[%s]'%var.unit)
        type_tag = '(' + (','.join(units)) + ')'
        return type_tag

    def addParam(self, name, data):
        for p in self.parameters:
            if p['label'] == name:
                raise errors.ParameterInUseError(name)
        d = dict(label=name, data=data)
        self.parameters.append(d)
    
    def getParameter(self, name, case_sensitive=True):
        for p in self.parameters:
            if case_sensitive:
                if p['label'] == name:
                    return p['data']
            else:
                if p['label'].lower() == name.lower():
                    return p['data']
        raise errors.BadParameterError(name)
    
    def getParamNames(self):
        return [ p['label']  for p in self.parameters ]

    def addComment(self, user, comment):
        self.comments.append((datetime.datetime.now(), user, comment))

    def getComments(self, limit, start):
        if limit is None:
            comments = self.comments[start:]
        else:
            comments = self.comments[start:start+limit]
        return comments, start + len(comments)

    def numComments(self):
        return len(self.comments)

class CsvListData(IniData):
    """
    Data backed by a csv-formatted file.

    Stores the entire contents of the file in memory as a list or numpy array
    """

    def __init__(self, filename, file_timeout=FILE_TIMEOUT, data_timeout=DATA_TIMEOUT):
        self.filename = filename
        self._file = SelfClosingFile(open_args=(filename, 'a+'), timeout=file_timeout)
        self.timeout = data_timeout
        self.infofile = filename[:-4] + '.ini'

    @property
    def file(self):
        return self._file()

    @property
    def version(self):
        return np.asarray([1,0,0], np.int32)

    @property
    def data(self):
        """Read data from file on demand.

        The data is scheduled to be cleared from memory unless accessed."""
        if not hasattr(self, '_data'):
            self._data = []
            self._datapos = 0
            self._timeout_call = reactor.callLater(self.timeout, self._on_timeout)
        else:
            self._timeout_call.reset(DATA_TIMEOUT)
        f = self.file
        f.seek(self._datapos)
        lines = f.readlines()
        self._data.extend([float(n) for n in line.split(',')] for line in lines)
        self._datapos = f.tell()
        return self._data

    def _on_timeout(self):
        del self._data
        del self._datapos
        del self._timeout_call

    def _saveData(self, data):
        f = self.file
        for row in data:
            # always save with dos linebreaks
            f.write(', '.join(DATA_FORMAT % v for v in row) + '\r\n')
        f.flush()

    def addData(self, data, transpose):
        if transpose:
            raise RuntimeError("Transpose specified for simple data format: not supported")
        if not len(data) or not isinstance(data[0], list):
            data = [data]
        if len(data[0]) != self.cols:
            raise errors.BadDataError(self.cols, len(data[0]))

        # append the data to the file
        self._saveData(data)

    def getData(self, limit, start, transpose):
        if transpose:
            raise RuntimeError("Transpose specified for simple data format: not supported")
        if limit is None:
            data = self.data[start:]
        else:
            data = self.data[start:start+limit]
        return data, start + len(data)

    def hasMore(self, pos):
        return pos < len(self.data)

class CsvNumpyData(CsvListData):
    """
    Data backed by a csv-formatted file.

    Stores the entire contents of the file in memory as a list or numpy array
    """

    def __init__(self, filename):
        self.filename = filename
        self._file = SelfClosingFile(open_args=(filename, 'a+'))
        self.infofile = filename[:-4] + '.ini'

    @property
    def file(self):
        return self._file()

    def _get_data(self):
        """Read data from file on demand.

        The data is scheduled to be cleared from memory unless accessed."""
        if not hasattr(self, '_data'):
            try:
                # if the file is empty, this line can barf in certain versions
                # of numpy.  Clearly, if the file does not exist on disk, this
                # will be the case.  Even if the file exists on disk, we must
                # check its size
                if self._file.size() > 0:
                    self._data = np.loadtxt(self.file, delimiter=',')
                else:
                    self._data = np.array([[]])
                if len(self._data.shape) == 1:
                    self._data.shape = (1, len(self._data))
            except ValueError:
                # no data saved yet
                # this error is raised by numpy <=1.2
                self._data = np.array([[]])
            except IOError:
                # no data saved yet
                # this error is raised by numpy 1.3
                self.file.seek(0)
                self._data = np.array([[]])
            self._timeout_call = reactor.callLater(DATA_TIMEOUT, self._on_timeout)
        else:
            self._timeout_call.reset(DATA_TIMEOUT)
        return self._data

    def _set_data(self, data):
        self._data = data

    data = property(_get_data, _set_data)

    def _on_timeout(self):
        del self._data
        del self._timeout_call

    def _saveData(self, data):
        f = self.file
        # always save with dos linebreaks (requires numpy 1.5.0 or greater)
        np.savetxt(f, data, fmt=DATA_FORMAT, delimiter=',', newline='\r\n')
        f.flush()

    def addData(self, data, transpose):
        if transpose:
            raise RuntimeError("Transpose specified for simple data format: not supported")
        data = np.asarray(data)

        # reshape single row
        if len(data.shape) == 1:
            data.shape = (1, data.size)

        # check row length
        if data.shape[-1] != self.cols:
            raise errors.BadDataError(self.cols, data.shape[-1])

        # append data to in-memory data
        if self.data.size > 0:
            self.data = np.vstack((self.data, data))
        else:
            self.data = data

        # append data to file
        self._saveData(data)

    def getData(self, limit, start, transpose):
        if transpose:
            raise RuntimeError("Transpose specified for simple data format: not supported")

        if limit is None:
            data = self.data[start:]
        else:
            data = self.data[start:start+limit]
        # nrows should be zero for an empty row
        nrows = len(data) if data.size > 0 else 0
        return data, start + nrows

    def hasMore(self, pos):
        # cheesy hack: if pos == 0, we only need to check whether
        # the filesize is nonzero
        if pos == 0:
            return os.path.getsize(self.filename) > 0
        else:
            nrows = len(self.data) if self.data.size > 0 else 0
            return pos < nrows

class HDF5MetaData(object):
    """
    Class to store metadata inside the file itself.  

    Like IniData, use this by subclassing.  I anticipate simply moving
    this code into the HDF5Dataset class once it is working, since we
    don't plan to support accessing HDF5 datasets with INI files once
    this version works.
    """
    def load(self):
        """
        Load and save do nothing because HDF5 metadata is accessed live
        """
        pass
    def save(self):
        """
        Load and save do nothing because HDF5 metadata is accessed live
        """
        pass

    def initialize_info(self, title, indep, dep):
        """
        Initializes the metadata for a newly created dataset.
        """
        self.dataset.attrs['Title'] = title
        t = time.time()
        self.dataset.attrs['Access Time'] = t
        self.dataset.attrs['Modification Time'] = t
        self.dataset.attrs['Creation Time'] = t

        dt = h5py.special_dtype(vlen=str)
        comment_type = [('Timestamp', np.float64), ('User', dt), ('Comment', dt)]
        self.dataset.attrs['Comments'] = np.ndarray((0,), dtype=comment_type)

        for idx, i in enumerate(indep):
            self.dataset.attrs['Independent%d.label'%idx] = i.label
            self.dataset.attrs['Independent%d.shape'%idx] = i.shape
            self.dataset.attrs['Independent%d.datatype'%idx] = i.datatype
            self.dataset.attrs['Independent%d.unit'%idx] = i.unit

        for idx, d, in enumerate(dep):
            self.dataset.attrs['Dependent%d.label'%idx] = d.label
            self.dataset.attrs['Dependent%d.legend'%idx] = d.legend
            self.dataset.attrs['Dependent%d.shape'%idx] = d.shape
            self.dataset.attrs['Dependent%d.datatype'%idx] = d.datatype
            self.dataset.attrs['Dependent%d.unit'%idx] = d.unit

    def access(self):
        self.dataset.attrs['Access Time'] = time.time()

    def getIndependents(self):
        rv = []
        for idx in xrange(sys.maxint):
            key = "Independent%d.label"%idx
            if key in self.dataset.attrs:
                label = self.dataset.attrs['Independent%d.label'%idx]
                shape = self.dataset.attrs['Independent%d.shape'%idx]
                datatype = self.dataset.attrs['Independent%d.datatype'%idx]
                unit = self.dataset.attrs['Independent%d.unit'%idx]
                rv.append(Independent(label, shape, datatype, unit))
            else:
                return rv

    def getDependents(self):
        rv = []
        for idx in xrange(sys.maxint):
            key = "Dependent%d.label"%idx
            if key in self.dataset.attrs:
                label = self.dataset.attrs['Dependent%d.label'%idx]
                legend = self.dataset.attrs['Dependent%d.legend'%idx]
                shape = self.dataset.attrs['Dependent%d.shape'%idx]
                datatype = self.dataset.attrs['Dependent%d.datatype'%idx]
                unit = self.dataset.attrs['Dependent%d.unit'%idx]
                rv.append(Dependent(label, legend, shape, datatype, unit))
            else:
                return rv

    def getRowType(self):
        column_types = []
        for col in self.getIndependents()+self.getDependents():
            base_type = col.datatype
            if base_type in ['v', 'c']:
                unit_tag = '[%s]'%col.unit
            else:
                unit_tag = ''
            if len(col.shape) > 1:
                shape_tag = '*%d'%(len(col.shape),)
                comment = '{' + ','.join([str(s) for s in col.shape]) + '}'
            elif col.shape[0] > 1:
                shape_tag = '*'
                comment = '{%d}' % col.shape[0]
            else:
                shape_tag = ''
                comment = ''
            column_types.append(shape_tag+base_type+unit_tag+comment)
        type_tag = '*(' + (','.join(column_types)) + ')'
        return type_tag

    def getTransposeType(self):
        column_type = []
        for col in self.getIndependents()+self.getDependents():
            base_type = col.datatype
            if base_type in ['v', 'c']:
                unit_tag = '[%s]'%col.unit
            else:
                unit_tag = ''
            if len(col.shape) > 1:
                shape_tag = '*%d'%(len(col.shape)+1,)
                comment = '{' + 'N,' + ','.join([str(s) for s in col.shape]) + '}'
            elif col.shape[0] > 1:
                shape_tag = '*2'
                comment = '{N,%d}'%(col.shape[0],)
            else:
                shape_tag = '*'
                comment = ''
            column_type.append(shape_tag+base_type+unit_tag+comment)
        type_tag = '(' + (','.join(column_type)) + ')'
        return type_tag

    def addParam(self, name, data):
        keyname = 'Param.%s' % (name,)
        value = labrad_urlencode(data)
        self.dataset.attrs[keyname] = value

    def getParameter(self, name, case_sensitive=True):
        """
        Get a parameter from the dataset.
        """
        keyname = 'Param.%s' % (name,)
        if case_sensitive:
            if keyname in self.dataset.attrs:
                return labrad_urldecode(self.dataset.attrs[keyname])
        else:
            for k in self.dataset.attrs:
                if k.lower == keyname.lower:
                    return labrad_urldecode(self.dataset.attrs[k])
        raise errors.BadParameterError(name)

    def getParamNames(self):
        """
        Get the names of all dataset parameters.

        Parameter names in the HDF5 file are prefixed with 'Param.' to avoid conflicts with
        the other metadata.
        """
        names = [ str(k[6:]) for k in self.dataset.attrs if k.startswith('Param.') ]
        return names

    def addComment(self, user, comment):
        """
        Add a comment to the dataset.
        """
        t = time.time()
        dt = h5py.special_dtype(vlen=str)

        comment_type = [('Timestamp', np.float64), ('User', dt), ('Comment', dt)]
        new_comment = np.array([(t, user, comment)], dtype=comment_type)
        old_comments = self.dataset.attrs['Comments']
        data = np.hstack((old_comments, new_comment))
        self.dataset.attrs.create('Comments', data, dtype=comment_type)

    def getComments(self, limit, start):
        """
        Get comments in [(datetime, username, comment), ...] format.
        """
        if limit is None:
            raw_comments = self.dataset.attrs['Comments'][start:]
        else:
            raw_comments = self.dataset.attrs['Comments'][start:start+limit]
        comments = [ (datetime.datetime.fromtimestamp(c[0]), str(c[1]), str(c[2])) for c in raw_comments ]
        return comments, start+len(comments)

    def numComments(self):
        return len(self.dataset.attrs['Comments'])

class ExtendedHDF5Data(HDF5MetaData):
    """Dataset backed by HDF5 file

    This supports the extended dataset format which allows each column
    to have a different type and to be arrays themselves.
    """

    def __init__(self, fh):
        self._file = fh
        if 'Version' not in self.file.attrs:
            self.file.attrs['Version'] = np.asarray([3, 0, 0], dtype=np.int32)
        self.version = np.asarray(self.file.attrs['Version'], np.int32)

    def initialize_info(self, title, indep, dep):
        """
        This is used to initialize the columns when creating a new dataset"
        """
        dtype = []
        for idx, col in enumerate(indep+dep):
            shape = col.shape
            ttag = col.datatype
            unit = col.unit
            if len(shape)==1 and shape[0]==1:
                shapestr = ""
            else:
                shapestr = str(tuple(shape))
            varname = 'f%d' % idx
            if unit!='' and ttag not in ['v', 'c']:
                raise RuntimeError("Unit %s specfied for datatype %s.  Only v and c may have units" % (unit, ttag))
            if ttag=='i':
                dtype.append((varname, shapestr+"i4"))
            elif ttag == 's':
                if shapestr:
                    raise ValueError("Cannot create string array column")
                dtype.append((varname, h5py.special_dtype(vlen=str)))
            elif ttag == 't':
                dtype.append((varname, shapestr+"i8"))
            elif ttag == 'v':
                dtype.append((varname, shapestr+"f8"))
            elif ttag == 'c':
                dtype.append((varname, shapestr+"c16"))
            else:
                raise RuntimeError("Invalid type tag %s" % (ttag,))

        self.file.create_dataset("DataVault", (0,), dtype=dtype, maxshape=(None,))
        HDF5MetaData.initialize_info(self, title, indep, dep)

    @property
    def file(self):
        return self._file()
    @property
    def dataset(self):
        return self.file["DataVault"]

    def addDataTranspose(self, data):
        """
        Add data from a list of column arrays.
        """
        new_rows = data[0].shape[0]
        old_rows = self.dataset.shape[0]
        self.dataset.resize((old_rows + new_rows,))
        new_data = np.zeros((new_rows,), self.dataset.dtype)
        for idx,col in enumerate(data):
            column_name = 'f{}'.format(idx)
            new_data[column_name] = col
        self.dataset[old_rows:(old_rows+new_rows)] = new_data

    def addData(self, data, transpose):
        """
        Adds one or more rows or data from a numpy struct array.
        """
        if transpose:
            self.addDataTranspose(data)
            return
        new_rows = len(data)
        old_rows = self.dataset.shape[0]
        self.dataset.resize((old_rows + new_rows,))
        self.dataset[old_rows:(old_rows+new_rows)] = data

    def getData(self, limit, start, transpose):
        """
        Get up to limit rows from a dataset.
        """
        if transpose:
            return self.getDataTranspose(limit, start)

        data, new_pos = self._getData(limit, start)
        row_data = [ tuple(row) for row in data ]
        return row_data, new_pos

    def getDataTranspose(self, limit, start):
        struct_data, new_pos = self._getData(limit, start)
        columns = []
        for idx in range(len(struct_data.dtype)):
            columns.append(struct_data['f%d'%idx])
        columns = tuple(columns)
        return columns, new_pos

    def _getData(self, limit, start):
        if limit is None:
            struct_data = self.dataset[start:]
        else:
            struct_data = self.dataset[start:start+limit]
        return struct_data, start+struct_data.shape[0]

    def __len__(self):
        return self.dataset.shape[0]

    def hasMore(self, pos):
        return pos < len(self)
        
class SimpleHDF5Data(HDF5MetaData):
    """
    Dataset backed by HDF5 file.  This is a very simple implementation
    that only supports a single 2-D dataset of all floats.  HDF5 files
    support multiple types, multiple dimensions, and a filesystem-like
    tree of datasets within one file.  Here, the single dataset is stored
    in /DataVault within the HDF5 file.
    """
    def __init__(self, fh):
        self._file = fh
        if 'Version' not in self.file.attrs:
            self.file.attrs['Version'] = np.asarray([2, 0, 0], dtype=np.int32)
        self.version = np.asarray(self.file.attrs['Version'], dtype=np.int32)

    def initialize_info(self, title, indep, dep):
        ncol = len(indep)+len(dep)
        dtype = [ ('f%d'%idx, np.float64) for idx in range(ncol) ]
        if "DataVault" not in self.file:
            self.file.create_dataset("DataVault", (0,), dtype=dtype, maxshape=(None,))
        HDF5MetaData.initialize_info(self, title, indep, dep)

    @property
    def file(self):
        return self._file()
    @property
    def dataset(self):
        return self.file["DataVault"]

    def addData(self, data, transpose):
        """
        Adds one or more rows or data from a 2D array of floats.
        """
        if transpose:
            raise RuntimeError("Transpose specified for simple data format: not supported")
        data = np.atleast_2d(np.asarray(data))
        new_rows = data.shape[0]
        old_rows = self.dataset.shape[0]
        if data.shape[1] != len(self.dataset.dtype):
            raise errors.BadDataError(len(self.dataset.dtype), data.shape[1])

        self.dataset.resize((old_rows + new_rows,))
        new_data = np.zeros((new_rows,), dtype=self.dataset.dtype)
        for col in range(data.shape[1]):
            field = "f%d" % (col,)
            new_data[field] = data[:,col]
        self.dataset[old_rows:(old_rows+new_rows)] = new_data

    def getData(self, limit, start, transpose):
        """
        Get up to limit rows from a dataset.
        """
        if transpose:
            raise RuntimeError("Transpose specified for simple data format: not supported")
        if limit is None:
            struct_data = self.dataset[start:]
        else:
            struct_data = self.dataset[start:start+limit]
        columns = []
        for idx in range(len(struct_data.dtype)):
            columns.append(struct_data['f%d'%idx])
        data = np.column_stack(columns)
        return data, start+data.shape[0]

    def __len__(self):
        return self.dataset.shape[0]

    def hasMore(self, pos):
        return pos < len(self)

def open_hdf5_file(filename):
    """Factory for HDF5 files.  

    We check the version of the file to construct the proper class.  Currently, only two
    options exist: version 2.0.0 -> legacy format, 3.0.0 -> extended format.
    Version 1 is reserved for CSV files.
    """
    fh = SelfClosingFile(h5py.File, open_args=(filename, 'a'))
    version = fh().attrs['Version']
    if version[0] == 2:
        return SimpleHDF5Data(fh)
    else:
        return ExtendedHDF5Data(fh)

def create_backend(filename, title, indep, dep, extended):
    hdf5_file = filename + '.hdf5'
    fh = SelfClosingFile(h5py.File, open_args=(hdf5_file, 'a'))
    if extended:
        data = ExtendedHDF5Data(fh)
    else:
        data = SimpleHDF5Data(fh)
    data.initialize_info(title, indep, dep)
    return data
    
def open_backend(filename):
    """Make a data object that manages in-memory and on-disk storage for a dataset.

    filename should be specified without a file extension. If there is an existing
    file in csv or binary format, we create a backend of the appropriate type. If
    no file exists, we create a new backend to store data in binary form.
    """
    csv_file = filename + '.csv'
    hdf5_file = filename + '.hdf5'

    if os.path.exists(csv_file):
        if use_numpy:
            return CsvNumpyData(csv_file)
        else:
            return CsvListData(csv_file)
    elif os.path.exists(hdf5_file):
        return open_hdf5_file(hdf5_file)
    else: # We should have already cehcked, this should not happen
        raise errors.DatasetNotFoundError(filename)
