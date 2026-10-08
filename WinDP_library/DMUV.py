#!/usr/bin/env python
# coding: utf-8

# importing  all the  functions defined in DMUV.py
#from DMUV import*

#WIND DIR-MAG to U-V
# N = 0°  ->  S  = U = 0, V = -1
# NE = 45° ->  SW = U = -1, V = -1
# E = 90° U -> W = -1, V = 0
# SE = 135° -> NW U = -1, V = 1
# S = 180° -> N = U = 0, V = 1
# SW = 225° -> NE = U = 1, V = 1
# W = 270° -> E = U = 1, V = 0
# NW = 315° -> SE =  U = 1, V = -1
#U = math.sin(math.radians(180+180))
#V = math.cos(math.radians(180+180))


def WINDdm2uv(DIR, MAG):
    import math
    import numpy as np
    U=np.zeros(len(DIR))
    V=np.zeros(len(DIR))
    
    for index in range(len(DIR)):
        if  DIR[index]<180:
            U[index] = MAG[index]*math.sin(math.radians(DIR[index]+180))
            V[index] = MAG[index]*math.cos(math.radians(DIR[index]+180))
        else:
            U[index] = MAG[index]*math.sin(math.radians(DIR[index]-180))
            V[index] = MAG[index]*math.cos(math.radians(DIR[index]-180))
   
    U = np.round(U, decimals = 3)
    V = np.round(V, decimals = 3)
    return U, V


#Test WINDdm2uv()
#D = [0,45,90,135,180,225,270,315]
#M = [1,1/0.707106781,1,1/1/0.707106781,1,1/0.707106781,1,1/0.707106781]
#wx,wy = WINDdm2uv(D,M)
#wx,wy

#WIND U-V VECTORS TO DIR-MAG
# N = 0°  ->  S  = U = 0, V = -1 -> atan(U/V)*180/math.pi
# NE = 45° ->  SW = U = -1, V = -1 -> atan(U/V)*180/math.pi
# E = 90° U -> W = U -1, V = 0 -> atan(U/V)*180/math.pi + 180
# SE = 135° -> NW U = -1, V = 1 -> atan(U/V)*180/math.pi +180
# S = 180° -> N = U = 0, V = 1 -> atan(U/V)*180/math.pi +180
# SW = 225° -> NE = U = 1, V = 1 -> atan(U/V)*180/math.pi +180
# W = 270° -> E = U = 1, V = 0 -> atan(U/V)*180/math.pi +180
# NW = 315° -> SE =  U = 1, V = -1 -> atan(U/V)*180/math.pi +360

def WINDuv2dm(U,V):
    import math
    import numpy as np
    DIR=np.zeros(len(U))
    MAG=np.zeros(len(U))
    
    for index in range(len(U)):
        if  U[index]>0.000000001 and V[index]<0:
            DIR[index] =  math.atan(U[index]/V[index])*180/math.pi+360
        elif V[index]>=0:
            DIR[index] =  math.atan(U[index]/V[index])*180/math.pi+180
        else:
            DIR[index] =  math.atan(U[index]/V[index])*180/math.pi
         
        MAG[index] = math.sqrt(U[index]**2 + V[index]**2)
        
    DIR = np.round(DIR, decimals = 3)
    MAG = np.round(MAG, decimals = 3)        
    return DIR,MAG
        
#Test WINDuv2dm() should return
#D = [0,45,90,135,180,225,270,315]
#M = [1,1/0.707106781,1,1/1/0.707106781,1,1/0.707106781,1,1/0.707106781]
#d,m = WINDuv2dm(wx,wy)
#d, m 

#WATER DIR-MAG TO U-V VECTORS
# N = 0°  ->  U = 0, V = 1
# NE = 45° U = 1, V = 1
# E = 90° U = 1, V = 0
# SE = 135° U = 1, V = -1
# S = 180°  U = 0, V = -1
# SW = 225°  U = -1, V = -1
# W = 270°  U = -1, V = 0
# NW = 315°  U = -1, V = 1

def WATERdm2uv(DIR, MAG):
    import math
    import numpy as np
    U=np.zeros(len(DIR))
    V=np.zeros(len(DIR))
    
    for index in range(len(DIR)):
        U[index] = MAG[index]*math.sin(math.radians(DIR[index]))
        V[index] = MAG[index]*math.cos(math.radians(DIR[index]))

    U = np.round(U, decimals = 3)
    V = np.round(V, decimals = 3)
    return U, V
    return U, V
#Test WATERdm2uv()
#D = [0,45,90,135,180,225,270,315]
#M = [1,1/0.707106781,1,1/1/0.707106781,1,1/0.707106781,1,1/0.707106781]
#u,v = WATERdm2uv(D,M)
#u,v




#WATER U-V TO DIR-MAG

def WATERuv2dm(U,V):
    import math
    import numpy as np
    DIR=np.zeros(len(U))
    MAG=np.zeros(len(U))
    
    for index in range(len(U)):
        if  V[index]<0:
            DIR[index] =  math.atan(U[index]/V[index])*180/math.pi+180 #quadrant 2 & 3
        elif U[index]<0 and V[index]>=0:
            DIR[index] =  math.atan(U[index]/V[index])*180/math.pi+360 #quadrant 4
        else:
            DIR[index] =  math.atan(U[index]/V[index])*180/math.pi #quadrant 1
         
        MAG[index] = math.sqrt(U[index]**2 + V[index]**2)
        
    DIR = np.round(DIR, decimals = 3)
    MAG = np.round(MAG, decimals = 3)    
    return DIR,MAG
        
#Test WINDuv2dm() should return
#D = [0,45,90,135,180,225,270,315]
#M = [1,1/0.707106781,1,1/1/0.707106781,1,1/0.707106781,1,1/0.707106781]
#d,m = WATERuv2dm(u,v)
#d, m  

