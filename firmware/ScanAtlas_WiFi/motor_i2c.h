#pragma once
#include <Arduino.h>
#include "motor_config.h"
#include "motor_common.h"
#include "MecanumCar_v2.h"

// Pilote I2C : la carte moteur reçoit un octet de puissance par canal (1..8).
// Moteur m : canal impair 2m+1 = un sens, canal pair 2m+2 = l'autre (« avant » pour la bibliothèque d'origine).
class MotorI2C : public MotorDrive<MotorI2C> {
  mecanumCar *bus=nullptr;
  void write(unsigned channel,unsigned duty){bus->PWM_OUT(uint8_t(channel),uint8_t(duty>255?255:duty));}
public:
  static const char *name(){return "I2C";}
  static int motorOf(int wheel){return I2C_WHEEL_MOTOR[wheel];}
  static int signOf(int wheel){return I2C_WHEEL_SIGN[wheel];}
  bool begin(){
    const int pins[2]={I2C_SDA_PIN,I2C_SCL_PIN};
    if(!motorPinsValid(pins,2))return false;
    if(!motorWheelMapValid(I2C_WHEEL_MOTOR,I2C_WHEEL_SIGN))return false;
    if(!bus)bus=new mecanumCar(I2C_SDA_PIN,I2C_SCL_PIN);  // Le constructeur configure SDA et SCL.
    if(!bus)return false;
    stop();return true;
  }
  void stop(){if(bus)for(unsigned ch=1;ch<=8;++ch)write(ch,0);}
  void wheel(unsigned motor,int power){
    if(!bus||motor>3)return;
    unsigned low=2*motor+1,high=low+1;
    // Même règle que le PWM : le canal opposé tombe à zéro avant d'activer le nouveau sens.
    if(power>0){write(low,0);write(high,unsigned(power>255?255:power));}
    else if(power<0){write(high,0);write(low,unsigned(-power>255?255:-power));}
    else{write(low,0);write(high,0);}
  }
};
