organization := "org.labrad"

name := "QubitServer"

version := "0.6.0"

resolvers += "bintray" at "http://jcenter.bintray.com/"

crossPaths := false // don't add scala version suffix to jars

libraryDependencies ++= Seq(
  "org.labrad" % "jlabrad" % "0.2.0-M1"
)

// use sbt-pack to create packaged, runnable version of qubit server
packSettings
packMain := Map("qubitserver" -> "org.labrad.qubits.QubitServer")
packResourceDir := Map(
  // copy contents of src/main/pack to the root of the packed archive
  (sourceDirectory in Compile).value / "pack" -> ""
)
