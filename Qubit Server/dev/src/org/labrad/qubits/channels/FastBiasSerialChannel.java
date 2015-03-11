package org.labrad.qubits.channels;

import org.labrad.data.Data;
import org.labrad.qubits.config.SetupPacket;

/**
 * Created by pomalley on 3/10/2015.
 * FastBias control via serial
 */
public class FastBiasSerialChannel extends FastBiasChannel {

  private int dcRackCard;
  private double voltage;
  private boolean configured;

  public FastBiasSerialChannel(String name) {
    super(name);
    configured = false;
  }

  public void setDCRackCard(int dcRackCard) {
    this.dcRackCard = dcRackCard;
  }

  public void setBias(double voltage) {
    this.voltage = voltage;
    configured = true;
  }

  public SetupPacket getSetupPacket() {
    if (!configured) {
      return null;
    }
    Data data = Data.ofType("(s)(s(wswwv[V]))");
    data.get(0).setString("Select Device", 0);
    data.get(1).setString("channel_set_voltage", 0)
            .setWord(dcRackCard, 1, 0)
            .setString(getDcFiberId().toString().toUpperCase(), 1, 1)
            .setWord(0, 1, 2)  // always use fine, never use coarse
            .setWord(1, 1, 3)  // "always 1 with FINE" -- the DC Rack server source code
            .setValue(voltage, 1, 4);

    String state = String.format("%d%s: voltage=%f",
            dcRackCard, getDcFiberId().toString(), voltage);
    return new SetupPacket(state, data);
  }
}
