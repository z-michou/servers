package org.labrad.qubits.templates;

import org.labrad.qubits.channels.FastBiasSerialChannel;
import org.labrad.qubits.enums.DcRackFiberId;
import org.labrad.qubits.resources.Resources;

import java.util.List;

/**
 * Created by pomalley on 3/10/2015.
 *
 */
public class FastBiasSerialChannelBuilder extends ChannelBuilderBase {

  public FastBiasSerialChannelBuilder (String name, List<String> params, Resources resources) {
    this.name = name;
    this.params = params;
    this.resources = resources;
  }

  @Override
  public FastBiasSerialChannel build() {
    String cardNumber = params.get(0);
    String fiberId = params.get(1);
    FastBiasSerialChannel ch = new FastBiasSerialChannel(this.name);
    ch.setDCRackCard(Integer.valueOf(cardNumber));
    ch.setBiasChannel(DcRackFiberId.fromString(fiberId));
    return ch;
  }
}
