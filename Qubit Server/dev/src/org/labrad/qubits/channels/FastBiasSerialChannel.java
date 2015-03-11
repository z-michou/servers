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

  public FastBiasSerialChannel(String name) {
    super(name);
  }

  public void setDCRackCard(int dcRackCard) {
    this.dcRackCard = dcRackCard;
  }

  public void setBias(double voltage) {
    this.voltage = voltage;
  }

  public SetupPacket getSetupPacket() {
    Data data = Data.ofType("(s)(swswwv)");
    data.get(0).setString("Select Device", 0);
    data.get(1).setString("channel_set_voltage", 0)
            .setWord(dcRackCard, 1)
            .setString(getDcFiberId().toString())
            .setWord(0)  // always use fine, never use coarse
            .setWord(1)  // "always 1 with FINE" -- the DC Rack server source code
            .setValue(voltage);

    String state = String.format("%d%s: voltage=%f",
            dcRackCard, getDcFiberId().toString(), voltage);

    return new SetupPacket(state, data);
  }
}
