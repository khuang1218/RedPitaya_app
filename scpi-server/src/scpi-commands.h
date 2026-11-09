/**
 * $Id: $
 *
 * @brief Red Pitaya Scpi server SCPI configuration and general command interface
 *
 * @Author Red Pitaya
 *
 * (c) Red Pitaya  http://www.redpitaya.com
 *
 */

#ifndef SCPI_COMMANDS_H_
#define SCPI_COMMANDS_H_

#include "scpi/scpi.h"
#include "uart_protocol.h"

// extern scpi_t scpi_context;

scpi_t* initContext(bool arduinoMode);
const scpi_command_t* rp_scpi_CommandsForVersion(uint32_t version);

#endif /* SCPI_COMMANDS_H_ */
