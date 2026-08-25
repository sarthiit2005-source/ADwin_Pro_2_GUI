'<ADbasic Header, Headerversion 001.001>
' Process_Number                 = 1
' Initial_Processdelay           = 1000
' Eventsource                    = Timer
' Control_long_Delays_for_Stop   = No
' Priority                       = High
' Version                        = 1
' ADbasic_Version                = 6.4.0
' Optimize                       = Yes
' Optimize_Level                 = 1
' Stacksize                      = 1000
' Info_Last_Save                 = LAPTOP-JE9IJP6D  LAPTOP-JE9IJP6D\sarth
'<Header End>
#INCLUDE ADwinPro_all.inc

DIM ADC_DATA[8] AS LONG

#DEFINE DAC1 PAR_1
#DEFINE DAC2 PAR_2
#DEFINE DAC3 PAR_3
#DEFINE DAC4 PAR_4
#DEFINE DAC5 PAR_5
#DEFINE DAC6 PAR_6
#DEFINE DAC7 PAR_7
#DEFINE DAC8 PAR_8

#DEFINE ADC1 PAR_9
#DEFINE ADC2 PAR_10
#DEFINE ADC3 PAR_11
#DEFINE ADC4 PAR_12
#DEFINE ADC5 PAR_13
#DEFINE ADC6 PAR_14
#DEFINE ADC7 PAR_15
#DEFINE ADC8 PAR_16

#DEFINE EMERGENCY_STOP PAR_17

#DEFINE DAC1_ZERO PAR_18
#DEFINE DAC2_ZERO PAR_19
#DEFINE DAC3_ZERO PAR_20
#DEFINE DAC4_ZERO PAR_21
#DEFINE DAC5_ZERO PAR_22
#DEFINE DAC6_ZERO PAR_23
#DEFINE DAC7_ZERO PAR_24
#DEFINE DAC8_ZERO PAR_25

#DEFINE PROCESS_DELAY PAR_26

#DEFINE COMMAND PAR_27
#DEFINE DONE PAR_28
#DEFINE STATE PAR_29
#DEFINE ABORTED PAR_30

#DEFINE CMD_NONE 0
#DEFINE CMD_SET_DAC 1
#DEFINE CMD_READ_ADC 2
#DEFINE CMD_SET_ALL_DAC 3

#DEFINE STATE_IDLE 0
#DEFINE STATE_DAC_APPLIED 1


INIT:

  Processdelay = PROCESS_DELAY

  COMMAND = CMD_NONE
  DONE = 0
  STATE = STATE_IDLE
  ABORTED = 0

  EMERGENCY_STOP = 0

  DAC1_ZERO = 0
  DAC2_ZERO = 0
  DAC3_ZERO = 0
  DAC4_ZERO = 0
  DAC5_ZERO = 0
  DAC6_ZERO = 0
  DAC7_ZERO = 0
  DAC8_ZERO = 0

  P2_DAC(3, 1, 32768)
  P2_DAC(3, 2, 32768)
  P2_DAC(3, 3, 32768)
  P2_DAC(3, 4, 32768)
  P2_DAC(3, 5, 32768)
  P2_DAC(3, 6, 32768)
  P2_DAC(3, 7, 32768)
  P2_DAC(3, 8, 32768)


EVENT:

  IF (EMERGENCY_STOP = 1) THEN

    P2_DAC(3, 1, 32768)
    P2_DAC(3, 2, 32768)
    P2_DAC(3, 3, 32768)
    P2_DAC(3, 4, 32768)
    P2_DAC(3, 5, 32768)
    P2_DAC(3, 6, 32768)
    P2_DAC(3, 7, 32768)
    P2_DAC(3, 8, 32768)

    COMMAND = CMD_NONE
    STATE = STATE_IDLE
    DONE = 0
    ABORTED = 1

  ELSE

    IF (COMMAND = CMD_SET_DAC) THEN

      IF (STATE = STATE_IDLE) THEN

        IF (DAC1_ZERO = 0) THEN
          P2_DAC(3, 1, DAC1)
        ELSE
          P2_DAC(3, 1, 32768)
        ENDIF

        IF (DAC2_ZERO = 0) THEN
          P2_DAC(3, 2, DAC2)
        ELSE
          P2_DAC(3, 2, 32768)
        ENDIF

        IF (DAC3_ZERO = 0) THEN
          P2_DAC(3, 3, DAC3)
        ELSE
          P2_DAC(3, 3, 32768)
        ENDIF

        IF (DAC4_ZERO = 0) THEN
          P2_DAC(3, 4, DAC4)
        ELSE
          P2_DAC(3, 4, 32768)
        ENDIF

        IF (DAC5_ZERO = 0) THEN
          P2_DAC(3, 5, DAC5)
        ELSE
          P2_DAC(3, 5, 32768)
        ENDIF

        IF (DAC6_ZERO = 0) THEN
          P2_DAC(3, 6, DAC6)
        ELSE
          P2_DAC(3, 6, 32768)
        ENDIF

        IF (DAC7_ZERO = 0) THEN
          P2_DAC(3, 7, DAC7)
        ELSE
          P2_DAC(3, 7, 32768)
        ENDIF

        IF (DAC8_ZERO = 0) THEN
          P2_DAC(3, 8, DAC8)
        ELSE
          P2_DAC(3, 8, 32768)
        ENDIF

        DONE = 0
        ABORTED = 0
        STATE = STATE_DAC_APPLIED

      ELSE

        DONE = 1
        COMMAND = CMD_NONE
        STATE = STATE_IDLE

      ENDIF

    ELSE

      IF (COMMAND = CMD_READ_ADC) THEN

        P2_Start_ConvF(2, 0FFh)
        P2_Wait_EOCF(2, 0FFh)
        P2_Read_ADCF8(2, ADC_DATA, 1)

        ADC1 = ADC_DATA[1]
        ADC2 = ADC_DATA[2]
        ADC3 = ADC_DATA[3]
        ADC4 = ADC_DATA[4]
        ADC5 = ADC_DATA[5]
        ADC6 = ADC_DATA[6]
        ADC7 = ADC_DATA[7]
        ADC8 = ADC_DATA[8]

        DONE = 1
        COMMAND = CMD_NONE
        STATE = STATE_IDLE
        ABORTED = 0

      ELSE

        IF (COMMAND = CMD_SET_ALL_DAC) THEN

          IF (STATE = STATE_IDLE) THEN

            IF (DAC1_ZERO = 0) THEN
              P2_DAC(3, 1, DAC1)
            ELSE
              P2_DAC(3, 1, 32768)
            ENDIF

            IF (DAC2_ZERO = 0) THEN
              P2_DAC(3, 2, DAC2)
            ELSE
              P2_DAC(3, 2, 32768)
            ENDIF

            IF (DAC3_ZERO = 0) THEN
              P2_DAC(3, 3, DAC3)
            ELSE
              P2_DAC(3, 3, 32768)
            ENDIF

            IF (DAC4_ZERO = 0) THEN
              P2_DAC(3, 4, DAC4)
            ELSE
              P2_DAC(3, 4, 32768)
            ENDIF

            IF (DAC5_ZERO = 0) THEN
              P2_DAC(3, 5, DAC5)
            ELSE
              P2_DAC(3, 5, 32768)
            ENDIF

            IF (DAC6_ZERO = 0) THEN
              P2_DAC(3, 6, DAC6)
            ELSE
              P2_DAC(3, 6, 32768)
            ENDIF

            IF (DAC7_ZERO = 0) THEN
              P2_DAC(3, 7, DAC7)
            ELSE
              P2_DAC(3, 7, 32768)
            ENDIF

            IF (DAC8_ZERO = 0) THEN
              P2_DAC(3, 8, DAC8)
            ELSE
              P2_DAC(3, 8, 32768)
            ENDIF

            DONE = 0
            ABORTED = 0
            STATE = STATE_DAC_APPLIED

          ELSE

            DONE = 1
            COMMAND = CMD_NONE
            STATE = STATE_IDLE

          ENDIF

        ENDIF

      ENDIF

    ENDIF

  ENDIF
