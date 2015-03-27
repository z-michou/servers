package org.labrad.qubits.channels;

/**
 * Represents channels that can implement the start delay function.
 * @author pomalley
 *
 */
public interface StartDelayChannel extends FpgaChannel {
  public void setStartDelay(int startDelay);
  public int getStartDelay();
}
