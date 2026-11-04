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
#define MOTOR_DRIVER MOTOR_DRIVER_I2C
#endif

// 2a) Profil PWM : utilisé seulement si MOTOR_DRIVER == MOTOR_DRIVER_PWM.
//
// >>> BROCHES : écrire ici le numéro de GPIO de l'ESP32 relié à chaque entrée de la carte moteur. <<<
// Chaque moteur Mx a deux entrées : A (un sens) et B (l'autre sens).
constexpr int PIN_M1A=5;
constexpr int PIN_M1B=18;
constexpr int PIN_M2A=19;
constexpr int PIN_M2B=21;
constexpr int PIN_M3A=2;
constexpr int PIN_M3B=4;
constexpr int PIN_M4A=16;
constexpr int PIN_M4B=17;
// GPIO acceptés : 0, 2, 4, 5, 12 à 19, 21 à 23, 25 à 27 (chacun une seule fois).
// Interdits : 1 et 3 (console USB), 6 à 11 (mémoire flash), 32 et 33 (lidar), 34 à 39 (entrées seulement).
// Une valeur interdite ou en double bloque le démarrage moteur, avec un message sur le moniteur série.
// Valeurs de départ d'après le câblage relevé : à vérifier sur chaque robot.
constexpr int MOTOR_PINS[8]={PIN_M1A,PIN_M1B,PIN_M2A,PIN_M2B,PIN_M3A,PIN_M3B,PIN_M4A,PIN_M4B};
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

// 3) Sens des axes (valables pour les deux pilotes) : -1 inverse un mouvement entier.
//    Surge = avancer / reculer, Sway = déplacement latéral gauche / droite, Yaw = rotation.
//    Le sway est inversé ici (-1) d'après l'essai sur le robot : Q (gauche) allait à droite.
#ifndef AXIS_SURGE_SIGN
#define AXIS_SURGE_SIGN 1
#endif
#ifndef AXIS_SWAY_SIGN
#define AXIS_SWAY_SIGN -1
#endif
#ifndef AXIS_YAW_SIGN
#define AXIS_YAW_SIGN 1
#endif

// 4) Échelle de puissance : le pourcentage 0..100 de l'application devient une valeur de PWM
//    de MOTOR_DUTY_MIN à MOTOR_DUTY_MAX (sur 0..255). 100 % = MOTOR_DUTY_MAX.
//    MOTOR_DUTY_MIN est le seuil de démarrage des moteurs (par exemple 50 si les roues ne
//    tournent pas aux petites valeurs) ; 0 = pas de seuil.
#ifndef MOTOR_DUTY_MIN
#define MOTOR_DUTY_MIN 0
#endif
#ifndef MOTOR_DUTY_MAX
#define MOTOR_DUTY_MAX 255
#endif

// Passer à true uniquement pour le diagnostic série, roues levées.
// Wi-Fi et lidar ne démarrent pas dans ce mode. Valable pour les deux pilotes.
constexpr bool MOTOR_DIAGNOSTIC=false;
