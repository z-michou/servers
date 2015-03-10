package org.labrad.qubits.jumptable;

import com.google.common.base.Preconditions;
import com.google.common.collect.Lists;
import org.labrad.data.Data;
import org.labrad.data.Request;

import java.util.Arrays;
import java.util.List;

/**
 * Created by pomalley on 2/13/15.
 *
 * Basic logic for the jump table.
 */
public class JumpTable {
  private final List<String> entryNames;
  private final List<Data> entryArguments;
  private long[] counters;
  private int countersUsed;

  public JumpTable() {
    entryNames = Lists.newArrayList();
    entryArguments = Lists.newArrayList();
    counters = new long[] {0, 0, 0, 0};   // TODO: get from hardware
    countersUsed = 0;
  }

  /**
   * Emtpy this jump table.
   */
  public void clear() {
    entryNames.clear();
    entryArguments.clear();
    counters = new long[] {0, 0, 0, 0};   // TODO: get from hardware
  }

  public void addEntry(String name, Data argument) {
    // TODO: type check the name and argument
    if (name.equals("CYCLE")) {
      List<Data> args = argument.getClusterAsList();
      Preconditions.checkArgument(args.size() == 4, "Cycle must have 4 arguments; currently has " + args.toString());
      if (countersUsed == 3) {     // TODO: get num counters from hardware
        throw new RuntimeException("More than 4 counters used in jump table.");
      } else {
        counters[countersUsed] = argument.get(2).getWord();
        argument.get(2).setWord(countersUsed);
        countersUsed += 1;
      }
    }

    entryNames.add(name);
    entryArguments.add(argument);
  }

  public void setCounters(long[] counters) {
    this.counters = counters;
  }

  public boolean equals(JumpTable other) {
    if (entryNames.size() != other.entryNames.size()) {
      return false;
    }
    for (int i=0; i<entryNames.size(); i++) {
      if (!(entryNames.get(i).equals(other.entryNames.get(i)) &&
            entryArguments.get(i).equals(other.entryArguments.get(i)))) {
        return false;
      }
    }
    return Arrays.equals(counters, other.counters);
  }

  /**
   * Add jump table packets to the FPGA server.
   * The correct DAC must already have been selected.
   * @param runRequest request to the GHz FPGA server
   */
  public void addPackets(Request runRequest) {
    runRequest.add("Clear Jump Table");
    runRequest.add("Set Jump Table Counters", Data.valueOf(counters));
    for (int i=0; i<entryNames.size(); i++) {
      runRequest.add("Add Jump Table Entry", Data.valueOf(entryNames.get(i)), entryArguments.get(i));
    }
  }
}
