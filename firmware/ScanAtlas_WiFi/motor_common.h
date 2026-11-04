#pragma once
#include "protocol.h"

// GPIO utilisables en sortie sur un ESP32 classique, hors flash, console et lidar.
inline bool motorGpioUsable(int p){
  return p==0||p==2||p==4||p==5||(p>=12&&p<=19)||(p>=21&&p<=23)||(p>=25&&p<=27);
}
// Liste de broches : toutes utilisables et sans doublon.
inline bool motorPinsValid(const int *pins,int count){
  for(int i=0;i<count;++i){
    if(!motorGpioUsable(pins[i]))return false;
    for(int j=0;j<i;++j)if(pins[i]==pins[j])return false;
  }
  return true;
}
// Association roue -> moteur (0..3, sans doublon) et polarités (+1 ou -1).
inline bool motorWheelMapValid(const int *motor,const int *sign){
  for(int i=0;i<4;++i){
    if(motor[i]<0||motor[i]>3||(sign[i]!=1&&sign[i]!=-1))return false;
    for(int j=0;j<i;++j)if(motor[i]==motor[j])return false;
  }
  return true;
}

// Logique commune aux deux pilotes. Le pilote dérivé fournit :
//   static int motorOf(int roue), static int signOf(int roue), void wheel(unsigned moteur,int puissance), void stop().
template<class Driver>
class MotorDrive {
  Driver &self(){return *static_cast<Driver*>(this);}
public:
  // Commande combinée : chaque roue reçoit son pourcentage mélangé (vx, vy, w).
  void drive(int vx,int vy,int w){
    int mixed[4];mecanumMix(vx,vy,w,mixed);
    for(int i=0;i<4;++i)self().wheel(Driver::motorOf(i),mixed[i]*Driver::signOf(i));
  }
  void apply(Motion m,unsigned pwm){
    // Roues mecanum en X : FL FR RL RR. Profil et polarités configurables.
    static const int signs[7][4]={{0,0,0,0},{1,1,1,1},{-1,-1,-1,-1},
       {-1,1,-1,1},{1,-1,1,-1},{-1,1,1,-1},{1,-1,-1,1}};
    if(unsigned(m)>6){self().stop();return;}
    pwm=pwm<100u?pwm:100u;  // Même plafond que le protocole et l'application.
    for(int i=0;i<4;++i)self().wheel(Driver::motorOf(i),signs[m][i]*Driver::signOf(i)*int(pwm));
  }
};
