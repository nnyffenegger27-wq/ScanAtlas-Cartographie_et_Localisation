#pragma once
// ============================================================================
//  Configuration moteurs ScanAtlas : un seul endroit à modifier selon le robot.
// ============================================================================

// 1) Choix du pilote moteur (un seul actif, décidé à la compilation) :
//    MOTOR_DRIVER_PWM : huit sorties PWM directes sur les entrées de la carte moteur.
//    MOTOR_DRIVER_I2C : carte moteur pilotée par bus I2C (bibliothèque MecanumCar_v2).
#define MOTOR_DRIVER_PWM 1
#define MOTOR_DRIVER_I2C 2
#ifndef MOTOR_DRIVER  // Peut aussi être imposé par un drapeau de compilation (-DMOTOR_DRIVER=2).
#define MOTOR_DRIVER MOTOR_DRIVER_PWM
#endif

// 2a) Profil PWM : utilisé seulement si MOTOR_DRIVER == MOTOR_DRIVER_PWM.
// Profil proposé à partir du câblage relevé, à vérifier sur chaque robot.
// Entrées fixes de la carte moteur : M1A M1B M2A M2B M3A M3B M4A M4B.
constexpr int MOTOR_PINS[8]={5,18,19,21,2,4,16,17};
// Ordre logique : avant gauche, avant droite, arrière gauche, arrière droite.
// Chaque valeur désigne M1..M4 (indices 0..3). L'emplacement reste à confirmer.
constexpr int WHEEL_MOTOR[4]={0,1,2,3};
constexpr int WHEEL_SIGN[4]={1,1,1,1};
constexpr unsigned MOTOR_PWM_HZ=20000;

// 2b) Profil I2C : utilisé seulement si MOTOR_DRIVER == MOTOR_DRIVER_I2C.
// Bus logiciel (bit-banging) vers la carte moteur à l'adresse 0x30 (fixée dans MecanumCar_v2.cpp).
constexpr int I2C_SDA_PIN=19;
constexpr int I2C_SCL_PIN=21;
// Moteurs I2C : 0 = « Upper_R » (canaux 1-2), 1 = « Upper_L » (3-4),
//               2 = « Lower_R » (5-6),        3 = « Lower_L » (7-8).
// Ordre logique des roues : avant gauche, avant droite, arrière gauche, arrière droite.
// Le profil d'origine du robot Keyestudio donne : AG = Upper_L, AD = Upper_R, ARG = Lower_L, ARD = Lower_R.
constexpr int I2C_WHEEL_MOTOR[4]={1,0,3,2};
// -1 inverse le sens d'une roue ; une puissance positive pilote le canal pair (2, 4, 6, 8).
constexpr int I2C_WHEEL_SIGN[4]={1,1,1,1};

// Passer à true uniquement pour le diagnostic série, roues levées.
// Wi-Fi et lidar ne démarrent pas dans ce mode. Valable pour les deux pilotes.
constexpr bool MOTOR_DIAGNOSTIC=false;
