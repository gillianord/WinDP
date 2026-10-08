#!/usr/bin/env python
# coding: utf-8

# In[1]:

def wind_notes(path,df,center,lon,lat,declination,error,fig):
    """
    Fills in the first sheet of wind data stats in excel template for wind notes. Returns max velocity which can be used to make vel_bins
    """
    import openpyxl 
    import numpy as np
    from .DMUV import WINDdm2uv
    from io import BytesIO
    from openpyxl.drawing.image import Image
    import math
    import shutil 
    import os
    
    # Obtener el directorio donde está este módulo
    module_dir = os.path.dirname(os.path.abspath(__file__))
    source_file_path = os.path.join(module_dir, 'VIENTO_notas_tablas_plantilla.xlsx')
    
    filename = f'VIENTO_notas_tablas_{center}.xlsx'
    destination_file_path = os.path.join(path, filename)
    shutil.copy(source_file_path, destination_file_path)
    
    wb = openpyxl.load_workbook(destination_file_path)   
    sheet = wb["NOTAS"]

    sheet.cell(row = 2, column = 2).value = filename[20:-5 ] 
    sheet.cell(row = 3, column = 2).value = lon
    sheet.cell(row = 4, column = 2).value = lat
    sheet.cell(row = 5, column = 2).value = df.index[0]
    sheet.cell(row = 6, column = 2).value = df.index[-1]
    if declination is not None:
        if np.ndim(declination) == 0:
            declination_values = [float(declination), float(declination)]
        else:
            declination_values = list(declination)
        sheet.cell(row = 8, column = 2).value = declination_values[0]
        sheet.cell(row = 9, column = 2).value = declination_values[-1]
    sheet.cell(row = 10, column = 2).value = error
    if fig is not None:
        buffer = BytesIO()
        fig.savefig(buffer, format='jpeg')
        buffer.seek(0)
        img = Image(buffer)
        sheet.add_image(img, 'A11')

    #Start and finish date
    sheet.cell(row = 5, column = 2).value = df.index[0]
    sheet.cell(row = 6, column = 2).value = df.index[-1]
    #Vel max, fecha max, dirección máx
    DF = df.WS
    id = DF.idxmax(skipna = True) 
    max_vel = df.WS[id]
    sheet.cell(row = 2, column = 5).value = df.WS[id]
    sheet.cell(row = 3, column = 5).value = id
    sheet.cell(row = 4, column = 5).value = df.WD[id]

    sheet.cell(row = 7, column = 5).value = len(df.WS)
    sheet.cell(row = 8, column = 5).value = max(df.WS)
    sheet.cell(row = 9, column = 5).value = min(df.WS)
    sheet.cell(row = 10, column = 5).value = np.nanmean(df.WS)
    sheet.cell(row = 11, column = 5).value = np.nanstd(df.WS)
    sheet.cell(row = 12, column = 5).value = np.nanpercentile(df.WS, 50)
    sheet.cell(row = 13, column = 5).value = np.nanpercentile(df.WS, 75)
    sheet.cell(row = 14, column = 5).value = np.nanpercentile(df.WS, 95)
    
    sheet.cell(row = 7, column = 6).value = len(df.WS_max)
    sheet.cell(row = 8, column = 6).value = max(df.WS_max)
    sheet.cell(row = 9, column = 6).value = min(df.WS_max)
    sheet.cell(row = 10, column = 6).value = np.nanmean(df.WS_max)
    sheet.cell(row = 11, column = 6).value = np.nanstd(df.WS_max)
    sheet.cell(row = 12, column = 6).value = np.nanpercentile(df.WS_max, 50)
    sheet.cell(row = 13, column = 6).value = np.nanpercentile(df.WS_max, 75)
    sheet.cell(row = 14, column = 6).value = np.nanpercentile(df.WS_max, 95)
    
    U,V = WINDdm2uv(df.WD,df.WS)
    
    sheet.cell(row = 7, column = 8).value = len(U)
    sheet.cell(row = 8, column = 8).value = max(U)
    sheet.cell(row = 9, column = 8).value = min(U)
    sheet.cell(row = 10, column = 8).value = np.nanmean(U)
    sheet.cell(row = 11, column = 8).value = np.nanstd(U)
    sheet.cell(row = 12, column = 8).value = np.nanpercentile(U, 50)
    sheet.cell(row = 13, column = 8).value = np.nanpercentile(U, 75)
    sheet.cell(row = 14, column = 8).value = np.nanpercentile(U, 95)
    
    sheet.cell(row = 7, column = 9).value = len(V)
    sheet.cell(row = 8, column = 9).value = max(V)
    sheet.cell(row = 9, column = 9).value = min(V)
    sheet.cell(row = 10, column = 9).value = np.nanmean(V)
    sheet.cell(row = 11, column = 9).value = np.nanstd(V)
    sheet.cell(row = 12, column = 9).value = np.nanpercentile(V, 50)
    sheet.cell(row = 13, column = 9).value = np.nanpercentile(V, 75)
    sheet.cell(row = 14, column = 9).value = np.nanpercentile(V, 95)

    sheet.cell(row = 7, column = 7).value = len(df.WD)
    sheet.cell(row = 8, column = 7).value = max(df.WD)
    sheet.cell(row = 9, column = 7).value = min(df.WD)
    
    u = np.nanmean(U)
    v = np.nanmean(V)
    if  u>0.000000001 and v<0: #2nd quadrant
        d =  math.atan(u/v)*180/math.pi+360
    elif v>=0: #1st and 4th quadrant
        d =  math.atan(u/v)*180/math.pi+180
    else: #3rd quadrant
        d =  math.atan(u/v)*180/math.pi
    sheet.cell(row = 10, column = 7).value = d
    u = np.nanstd(U)
    v = np.nanstd(V)
    if  u>0.000000001 and v<0: #2nd quadrant
        d =  math.atan(u/v)*180/math.pi+360
    elif v>=0: #1st and 4th quadrant
        d =  math.atan(u/v)*180/math.pi+180
    else: #3rd quadrant
        d =  math.atan(u/v)*180/math.pi
    sheet.cell(row = 11, column = 7).value = d

    wb.save(destination_file_path)
    return filename

def wind_incident_tables(path,filename,df,vel_bins): 
    """
    Fills in the second sheet of wind incident tabels in excel template for wind notes. Inludes incident tabels sampling data every 4 hours
    """
    import openpyxl 
    import numpy as np
    hora = np.arange(0,24,4)
    #vel_bins  = np.arange(0,17,2)
    vel_bin_labels=[]
    for i in range(len(vel_bins)-1):
        if i<len(vel_bins)-2:
            vel_bin_labels.append('['+str(vel_bins[i])+','+str(vel_bins[i+1])+'(')
        else:
            vel_bin_labels.append('['+str(vel_bins[i])+','+str(vel_bins[i+1])+']')
            
    #rows - velocity bins, columns - 8 cardinal directions 
    wb = openpyxl.load_workbook(path+'/'+filename)   
    sheet = wb["TABLAS_INCIDENCIA"]  
    
    max_med_ds = np.zeros((3,8))
    Tabla_incidencia = np.zeros(((len(vel_bins)-1), 8))
    
    Dn = df.WS[(df.WD>=360-45/2) | (df.WD<45/2)]  #Filter data from North
    if len(Dn)>0:
        max_med_ds[0,0]=np.max(Dn)
        max_med_ds[1,0]=np.mean(Dn)
        max_med_ds[2,0]=np.std(Dn)
    else:
        max_med_ds[:,0]=0
    sheet.cell(row = 13, column = 3).value = max_med_ds[0,0]
    sheet.cell(row = 14, column = 3).value = max_med_ds[1,0]
    sheet.cell(row = 15, column = 3).value = max_med_ds[2,0]
    for j in range(1,8): #NW to NE - j index for non-north directions
        D  = df.WS[(df.WD>=45*j-45/2) & (df.WD<45*j+45/2)]
        if len(D)>0:
            max_med_ds[0,j]=np.max(D)
            max_med_ds[1,j]=np.mean(D)
            max_med_ds[2,j]=np.std(D)
        else:
            max_med_ds[:,j]=0
        sheet.cell(row = 13, column = 3+j).value = max_med_ds[0,j]
        sheet.cell(row = 14, column = 3+j).value = max_med_ds[1,j]
        sheet.cell(row = 15, column = 3+j).value = max_med_ds[2,j]
        for k in range(len(vel_bins)-1): 
            sheet.cell(row = 3+k, column = 2).value = vel_bin_labels[k]
            Vn = Dn[(Dn>=vel_bins[k]) & (Dn<vel_bins[k+1])]  #Filter data from velocity bin
            Tabla_incidencia[k,0] = len(Vn) #Number of observations
            sheet.cell(row = 3+k, column = 3).value = Tabla_incidencia[k,0]
            V = D[(D>=vel_bins[k]) & (D<vel_bins[k+1])]  #Filter data from velocity bin
            Tabla_incidencia[k,j] = len(V) #Number of observations
            sheet.cell(row = 3+k, column = 3+j).value = Tabla_incidencia[k,j]
            
    hora=np.arange(0,24,4)
    
    for i in range(len(hora)):
        DF = df[(df.index.hour==hora[i])] #Filter data from a particular hour
        max_med_ds = np.zeros((3,8))
        Tabla_incidencia = np.zeros(((len(vel_bins)-1), 8))
        Dn = DF.WS[(DF.WD>=360-45/2) | (DF.WD<45/2)]  #Filter data from North
        if len(Dn)>0:
            max_med_ds[0,0]=np.max(Dn)
            max_med_ds[1,0]=np.mean(Dn)
            max_med_ds[2,0]=np.std(Dn)
        else:
            max_med_ds[:,0]=0
        sheet.cell(row = 16*(i+1)+13, column = 3).value = max_med_ds[0,0]
        sheet.cell(row = 16*(i+1)+14, column = 3).value = max_med_ds[1,0]
        sheet.cell(row = 16*(i+1)+15, column = 3).value = max_med_ds[2,0]
        for j in range(1,8): #NW to NE - j index for non-north directions
            D  = DF.WS[(DF.WD>=45*j-45/2) & (DF.WD<45*j+45/2)]
            if len(D)>0:
                max_med_ds[0,j]=np.max(D)
                max_med_ds[1,j]=np.mean(D)
                max_med_ds[2,j]=np.std(D)
            else:
                max_med_ds[:,j]=0
            sheet.cell(row = 16*(i+1)+13, column = 3+j).value = max_med_ds[0,j]
            sheet.cell(row = 16*(i+1)+14, column = 3+j).value = max_med_ds[1,j]
            sheet.cell(row = 16*(i+1)+15, column = 3+j).value = max_med_ds[2,j]
            for k in range(len(vel_bins)-1): 
                sheet.cell(row = 3+16*(i+1)+k, column = 2).value = vel_bin_labels[k]
                Vn = Dn[(Dn>=vel_bins[k]) & (Dn<vel_bins[k+1])]  #Filter data from velocity bin
                Tabla_incidencia[k,0] = len(Vn) #Number of observations
                sheet.cell(row = 3+16*(i+1)+k, column = 3).value = Tabla_incidencia[k,0]
                V = D[(D>=vel_bins[k]) & (D<vel_bins[k+1])]  #Filter data from velocity bin
                Tabla_incidencia[k,j] = len(V) #Number of observations
                sheet.cell(row = 3+16*(i+1)+k, column = 3+j).value = Tabla_incidencia[k,j]
                
    wb.save(path+'/'+filename)

def monthlabels(df):
    import numpy as np
    import pandas as pd
    año=[]
    if  df.index[-1].year == df.index[0].year: #case 1 - no change in year
        meses = np.arange(df.index[0].month, df.index[-1].month+1)
        for i in range(len(meses)):
            año.append(df.index[0].year)
    elif df.index[-1].year - df.index[0].year == 1: #case 2 - change in year
        meses = np.arange(df.index[0].month, 13) #go to december
        meses = np.append(meses, np.arange(1,df.index[-1].month+1)) #then january til end  
        for i in range(13-meses[0]):
            año.append(df.index[0].year)
        for i in range(len(meses)-(13-meses[0])):
            año.append(df.index[-1].year) 
    elif df.index[-1].year - df.index[0].year == 2: #case 3 - 1 to 2 years
        meses = np.arange(df.index[0].month, 13) #go to december
        meses = np.append(meses, np.arange(1, 13)) 
        meses = np.append(meses, np.arange(1,df.index[-1].month+1)) #then january til end 
        for i in range(13-meses[0]):
            año.append(df.index[0].year)
        for i in range(12):
            año.append(df.index[0].year+1)
        for i in range(len(meses)-(13-meses[0]+12)):
            año.append(df.index[-1].year)
    months = ['enero','febrero','marzo','abril','mayo','junio','julio','agosto','septiembre','octubre','noviembre','diciembre']
    monthyear_labels = []
    for i in range(len(meses)):
        monthyear_labels.append(months[meses[i]-1]+'-'+str(año[i]))        
    return meses, año, monthyear_labels
   
def wind_incident_tables_months(path,filename,df,vel_bins): 
    """
    Fills in the second sheet of wind incident tabels in excel template for wind notes. Inludes incident tabels sampling data every 4 hours
    """
    import openpyxl 
    import numpy as np
    
    vel_bin_labels=[]
    for i in range(len(vel_bins)-1):
        if i<len(vel_bins)-2:
            vel_bin_labels.append('['+str(vel_bins[i])+','+str(vel_bins[i+1])+'(')
        else:
            vel_bin_labels.append('['+str(vel_bins[i])+','+str(vel_bins[i+1])+']')
    
    meses, año, monthyear_labels = monthlabels(df)
    
    wb = openpyxl.load_workbook(path+'/'+filename)      
    #Stuff needed for figure
    XLABELS = []
    MAX = np.zeros(len(meses))
    MEAN = np.zeros(len(meses))
    P5 = np.zeros(len(meses))
    P95 = np.zeros(len(meses))
    hourly_mean_month = np.zeros((len(meses),24))
        
    for i in range(len(meses)):
        DF = df[(df.index.month==meses[i]) & (df.index.year==año[i])] #Filter data from a particular month
        XLABELS.append(str(DF.index[0])[5:7]+'/'+str(DF.index[0])[2:4])
        sheet = wb["ANÁLISIS_MENSUAL"]  
        sheet.cell(row = 1, column = i+2).value = monthyear_labels[i][:-5]#.upper()
        sheet.cell(row = 2, column = i+2).value = len(DF.WS)
        MAX[i] = np.max(DF.WS)
        sheet.cell(row = 3, column = i+2).value = np.max(DF.WS)
        sheet.cell(row = 4, column = i+2).value = np.min(DF.WS)
        MEAN[i]  = np.mean(DF.WS)
        sheet.cell(row = 5, column = i+2).value = np.mean(DF.WS)
        sheet.cell(row = 6, column = i+2).value = np.std(DF.WS)
        sheet.cell(row = 7, column = i+2).value = np.nanpercentile(DF.WS, 50)
        P5[i] = np.nanpercentile(DF.WS, 5)
        sheet.cell(row = 8, column = i+2).value = np.nanpercentile(DF.WS, 5)
        P95[i] = np.nanpercentile(DF.WS, 95)
        sheet.cell(row = 9, column = i+2).value = np.nanpercentile(DF.WS, 95)   
    
        for h in range(24):
            dfh = DF[DF.index.hour == h]
            hourly_mean_month[i,h] = np.nanmean(dfh.WS)
            
        sheet = wb["TABLAS_INCIDENCIA_MENSUAL"]      
    
        max_med_ds = np.zeros((3,8))#start by filling in max, mean and standard deviation
        
        Tabla_incidencia = np.zeros(((len(vel_bins)-1), 8))
        Dn = DF.WS[(DF.WD>=360-45/2) | (DF.WD<45/2)]  #Filter data from North
        if len(Dn)>0:
            max_med_ds[0,0]=np.max(Dn)
            max_med_ds[1,0]=np.mean(Dn)
            max_med_ds[2,0]=np.std(Dn)
        else: #fill in zeros to avoid nans if no observations
            max_med_ds[:,0]=0
            
        sheet.cell(row = 16*i+13, column = 3).value = max_med_ds[0,0]
        sheet.cell(row = 16*i+14, column = 3).value = max_med_ds[1,0]
        sheet.cell(row = 16*i+15, column = 3).value = max_med_ds[2,0]
        
        for j in range(1,8): #NE to NW - j index for non-north directions
            D  = DF.WS[(DF.WD>=45*j-45/2) & (DF.WD<45*j+45/2)]
            if len(D)>0:
                max_med_ds[0,j]=np.max(D)
                max_med_ds[1,j]=np.mean(D)
                max_med_ds[2,j]=np.std(D)
            else:
                max_med_ds[:,j]=0
                
            sheet.cell(row = 16*i+13, column = 3+j).value = max_med_ds[0,j]
            sheet.cell(row = 16*i+14, column = 3+j).value = max_med_ds[1,j]
            sheet.cell(row = 16*i+15, column = 3+j).value = max_med_ds[2,j]
            
            for k in range(len(vel_bins)-1): 
                if i == 0:
                    sheet.cell(row = 3+k, column = 2).value = vel_bin_labels[k]
                else:
                    sheet.cell(row = 3+16*i+k, column = 2).value = vel_bin_labels[k]
                    
                Vn = Dn[(Dn>=vel_bins[k]) & (Dn<vel_bins[k+1])]  #Filter data from velocity bin
                Tabla_incidencia[k,0] = len(Vn) #Number of observations
                sheet.cell(row = 3+16*i+k, column = 3).value = Tabla_incidencia[k,0]
                V = D[(D>=vel_bins[k]) & (D<vel_bins[k+1])]  #Filter data from velocity bin
                Tabla_incidencia[k,j] = len(V) #Number of observations
                sheet.cell(row = 3+16*i+k, column = 3+j).value = Tabla_incidencia[k,j]
    wb.save(path+'/'+filename)
    return XLABELS,MAX,MEAN,P5,P95