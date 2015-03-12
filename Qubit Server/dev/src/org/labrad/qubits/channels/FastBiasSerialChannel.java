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
  private String dac;

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
    int dac_num, rc_time_constant;
    if (!configured) {
      return null;
    }
    if (dac.toLowerCase().equals("dac0")) {
      dac_num = 0;
      rc_time_constant = 1;
    } else if (dac.toLowerCase().equals("dac1slow")) {
      dac_num = 1;
      rc_time_constant = 1;
    } else if (dac.toLowerCase().equals("dac1")) {
      dac_num = 1;
      rc_time_constant = 0;
    } else {
      throw new IllegalArgumentException("DAC setting must be one of 'dac0', 'dac1', or 'dac1slow'");
    }
    Data data = Data.ofType("(s)(s(wswwv[V]))");
    data.get(0).setString("Select Device", 0);
    data.get(1).setString("channel_set_voltage", 0)
            .setWord(dcRackCard, 1, 0)
            .setString(getDcFiberId().toString().toUpperCase(), 1, 1)
            .setWord(dac_num, 1, 2)
            .setWord(rc_time_constant, 1, 3)
            .setValue(voltage, 1, 4);

    String state = String.format("%d%s: voltage=%f dac=%s",
            dcRackCard, getDcFiberId().toString(), voltage, dac);
    return new SetupPacket(state, data);
  }

  public void setDac(String dac) {
    this.dac = dac;
  }
}
