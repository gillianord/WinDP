#!/usr/bin/env python
# coding: utf-8

# In[40]:


def _draw_wind_rose(rose_ax, wd, ws, rose_bins):
    """Redraw a wind rose for the provided samples.

    WindroseAxes does not reliably redraw after ``clear()``, so the axes is
    replaced in-place and the new axes is returned.
    """
    import matplotlib.pyplot as plt
    import matplotlib.ticker as mtick

    fig = rose_ax.figure
    subplot_spec = rose_ax.get_subplotspec()

    # Windrose legends often cannot be removed with Artist.remove().
    # Dropping the axes itself is enough; hide any leftover figure legends.
    rose_ax.remove()
    for extra_legend in list(getattr(fig, "legends", [])):
        try:
            extra_legend.remove()
        except NotImplementedError:
            extra_legend.set_visible(False)

    rose_ax = fig.add_subplot(subplot_spec, projection="windrose")

    if len(wd) == 0 or len(ws) == 0:
        return rose_ax

    cm = plt.get_cmap("jet")
    rose_ax.bar(
        wd,
        ws,
        normed=True,
        blowto=False,
        nsector=8,
        opening=1,
        bins=rose_bins,
        cmap=cm,
        edgecolor="k",
    )
    rose_ax.yaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
    rose_ax.set_legend(loc="center left", bbox_to_anchor=(1.08, 0.5))
    return rose_ax


def wind_rose_polar_timeseries(path, df, vel_bins):
    """Create the wind rose, polar scatter, and wind-speed time series.

    ``path`` is retained for compatibility with existing callers.  The
    returned artist dictionary lets GUI callers update the selected point
    without rebuilding the whole figure.
    """
    import numpy as np
    import matplotlib.pyplot as plt
    from matplotlib.figure import Figure
    from windrose import WindroseAxes  # noqa: F401 - registers the projection

    del path
    if df.empty:
        raise ValueError("Cannot plot an empty wind data set.")
    missing_columns = {"WD", "WS"}.difference(df.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"Wind data is missing required column(s): {missing}")

    wd = np.asarray(df["WD"], dtype=float)
    ws = np.asarray(df["WS"], dtype=float)
    finite = np.isfinite(wd) & np.isfinite(ws)
    if not finite.any():
        raise ValueError("WD and WS contain no finite values to plot.")

    rose_bins = np.asarray(vel_bins, dtype=float)
    if rose_bins.ndim != 1 or len(rose_bins) < 2:
        raise ValueError("vel_bins must contain at least two values.")
    rose_bins = rose_bins[:-1]

    fig = Figure(figsize=(14, 7),facecolor="whitesmoke")
    grid = fig.add_gridspec(
        3,
        2,
        width_ratios=[1.05, 1],
        height_ratios=[1, 1, 0.95],
        left=0.04,
        right=0.90,
        top=0.94,
        bottom=0.07,
        wspace=0.28,
        hspace=0.32,
    )
    rose_ax = fig.add_subplot(grid[0:2, 0], projection="windrose")
    polar_ax = fig.add_subplot(grid[0:2, 1], projection="polar")
    timeseries_ax = fig.add_subplot(grid[2, :])

    # Dummy axes first so windrose sectors render with curved edges.
    hist_ax = plt.Axes(fig, [0.1, 0.1, 0.8, 0.8])
    hist_ax.bar(np.array([1]), np.array([1]))
    rose_ax = _draw_wind_rose(rose_ax, wd[finite], ws[finite], rose_bins)

    directions_radians = np.deg2rad(wd)
    polar_points = polar_ax.scatter(
        directions_radians,
        ws,
        s=5,
        c="skyblue",
        edgecolors="dodgerblue",
        linewidths=0.7,
        alpha=0.8,
        picker=5,
    )
    selected_position = int(np.nanargmax(ws))
    polar_selection = polar_ax.scatter(
        [directions_radians[selected_position]],
        [ws[selected_position]],
        s=10,
        c="magenta",
        edgecolors="darkmagenta",
        zorder=5,
    )
    polar_ax.set_theta_zero_location("N")
    polar_ax.set_theta_direction(-1)
    polar_ax.set_rmax(max(float(np.ceil(np.nanmax(ws))) + 1.0, 1.0))

    gust_line = None
    gust_speeds = None
    if "WS_max" in df.columns:
        gust_speeds = np.asarray(df["WS_max"], dtype=float)
        # Gust under wind speed; above direction (drawn on the twin axis).
        (gust_line,) = timeseries_ax.plot(
            df.index,
            gust_speeds,
            color="crimson",
            linewidth=0.8,
            zorder=2,
            visible=False,
            label="Wind gust",
            picker=False,
        )

    (timeseries_line,) = timeseries_ax.plot(
        df.index,
        ws,
        color="skyblue",
        linewidth=0.8,
        zorder=3,
        label="Wind speed",
        picker=False,
    )
    timeseries_points = timeseries_ax.scatter(
        df.index,
        ws,
        s=8,
        c="skyblue",
        linewidths=0.5,
        picker=6,
        zorder=4,
    )
    timeseries_selection = timeseries_ax.scatter(
        [df.index[selected_position]],
        [ws[selected_position]],
        s=10,
        c="magenta",
        edgecolors="darkmagenta",
        zorder=5,
        picker=False,
    )
    timeseries_ax.set_ylabel("Wind speed (m/s)")
    timeseries_ax.grid(True)
    timeseries_ax.margins(0)

    # Twin axis sits below the primary axes so wind-speed picking still works.
    direction_ax = timeseries_ax.twinx()
    (direction_line,) = direction_ax.plot(
        df.index,
        wd,
        color="black",
        linewidth=0.8,
        zorder=1,
        visible=False,
        label="Direction",
        picker=False,
    )
    battery_line = None
    battery_voltages = None
    if "BattV" in df.columns:
        battery_voltages = np.asarray(df["BattV"], dtype=float)
        (battery_line,) = direction_ax.plot(
            df.index,
            battery_voltages,
            color="darkgreen",
            linewidth=0.8,
            zorder=1,
            visible=False,
            label="Battery",
            picker=False,
        )
    direction_ax.set_ylim(0, 360)
    direction_ax.set_ylabel("Direction (°)", color="black", labelpad=8)
    direction_ax.tick_params(axis="y", colors="black", pad=3)
    direction_ax.grid(True)
    direction_ax.margins(0)
    direction_ax.spines["right"].set_visible(False)
    direction_ax.yaxis.set_visible(False)
    direction_ax.set_zorder(timeseries_ax.get_zorder() - 1)
    direction_ax.patch.set_visible(False)
    direction_ax.set_navigate(False)
    timeseries_ax.set_zorder(direction_ax.get_zorder() + 1)
    timeseries_ax.patch.set_visible(False)

    artists = {
        "rose_axis": rose_ax,
        "polar_axis": polar_ax,
        "timeseries_axis": timeseries_ax,
        "direction_axis": direction_ax,
        "polar_points": polar_points,
        "polar_selection": polar_selection,
        "timeseries_line": timeseries_line,
        "timeseries_points": timeseries_points,
        "timeseries_selection": timeseries_selection,
        "gust_line": gust_line,
        "direction_line": direction_line,
        "battery_line": battery_line,
        "directions_radians": directions_radians,
        "polar_offsets": np.column_stack([directions_radians, ws]),
        "timestamps": np.asarray(df.index),
        "wind_directions": wd,
        "wind_speeds": ws,
        "gust_speeds": gust_speeds,
        "battery_voltages": battery_voltages,
        "rose_bins": rose_bins,
        "selected_position": selected_position,
    }
    return fig, artists

def wind_report_figures(path, df,vel_bins):
    import numpy as np
    import matplotlib.pyplot as plt
    from windrose import WindroseAxes
    import math
    import matplotlib.ticker as mtick
    from .DMUV import WINDdm2uv
    import math
    
    vel_bins_rose = vel_bins[:-1]
    wd = df.WD #wind speed 10 min average
    ws = df.WS #wind direction
    
    fig = plt.figure(figsize=(14, 7))
    ax0 = plt.subplot2grid((1, 2), (0, 0), colspan=1,projection='windrose')
    #Parche - Si los sectores no son curvadas, hacer un eje dummy primero arregla esto. 
    #Discomentar las siguentes 4 líneas.
    #fig = plt.figure()
    rect = [0.1, 0.1, 0.8, 0.8]
    hist_ax = plt.Axes(fig,rect)
    hist_ax.bar(np.array([1]), np.array([1]))
    cm = plt.get_cmap('jet')
    ax0.bar(wd, ws, normed=True, blowto=False, nsector=8, opening=1, bins=vel_bins_rose, cmap=cm, edgecolor='k')#Controlar tick y etiquetas del eje radial
    #ax.set_yticks(np.arange(10,30,10))
    #ax.set_yticklabels(np.arange(10,30,10),fontweight="bold")
    ax0.yaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
    ax0.set_xticklabels(['E','NE','N','NO','O','SO','S','SE'], fontweight='bold', fontsize=12)  
    legend = ax0.set_legend(bbox_to_anchor=(-0.21, 0.5),loc='center')
    for text in legend.get_texts():
        text.set_fontweight("bold")
        text.set_fontsize(12)
    table = ax0._info['table']
    table_index = np.argmin(np.sum(table,axis=0))
    table_value = [2,1,0,7,6,5,4,3]
    ax0_label_position = table_value[table_index]*45 #set axis label to where % of observations is lowest  
    ax0.set_rlabel_position(ax0_label_position)
    ax0.set_rmax(np.ceil(max(np.sum(table,axis=0)))+1) #set axis to where frequency is highest
    ax0.set_title('Rosa de viento',fontweight='bold',pad=20)  
    
    ax1 = plt.subplot2grid((1, 2), (0, 1), colspan=1, projection='polar')
    wd_radians = [math.radians(index) for index in wd] #the same as #wd_radians = [i/180*np.pi for i in  wd]
    ax1.scatter(wd_radians,ws, s=50, c ='yellow', edgecolor='k')
    i = max(enumerate(ws), key = lambda x: x[1])[0] 
    ax1.scatter(wd_radians[i], ws[i],s=80, c ='r', edgecolor='k')
    ax1.set_theta_zero_location('N')
    ax1.set_theta_direction(-1)
    ax1.set_rmax(np.round(max(df.WS),0)+1) 
    ax1.set_xticklabels(['N','NE','E','SE','S','SO','O','NO'], fontweight='bold', fontsize=12)  
    ax1.set_title("Diagrama polar de dispersión", fontweight='bold',pad=20)  
    label_position=ax1.get_rlabel_position()
    ax1_label_position = np.argmin(np.sum(table[3:,:],axis=0))*45 #lowest % of observations in higher bins 
    ax1.set_rlabel_position(ax1_label_position) 
    ax1.text(np.radians(ax1_label_position+3),ax1.get_rmax()*0.75,'[m/s]', fontweight='bold', fontsize=14,
            rotation=0,ha='right',va='center')
    plt.tight_layout()
    plt.savefig(path+'/1-Rosa+Polar.jpg',dpi=200)

    fig = plt.figure(figsize=(7, 7))
    ax0 = plt.subplot2grid((1, 1), (0, 0), colspan=1,projection='windrose')
    #Parche - Si los sectores no son curvadas, hacer un eje dummy primero arregla esto. 
    #Discomentar las siguentes 4 líneas.
    #fig = plt.figure()
    rect = [0.1, 0.1, 0.8, 0.8]
    hist_ax = plt.Axes(fig,rect)
    hist_ax.bar(np.array([1]), np.array([1]))
    cm = plt.get_cmap('jet')
    ax0.bar(wd, ws, normed=True, blowto=False, nsector=8, opening=1, bins=vel_bins_rose, cmap=cm, edgecolor='k')#Controlar tick y etiquetas del eje radial
    #ax.set_yticks(np.arange(10,30,10))
    #ax.set_yticklabels(np.arange(10,30,10),fontweight="bold")
    ax0.yaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
    ax0.set_xticklabels(['E','NE','N','NO','O','SO','S','SE'], fontweight='bold', fontsize=12)  
    legend = ax0.set_legend(bbox_to_anchor=(-0.21, 0.5),loc='center')
    for text in legend.get_texts():
        text.set_fontweight("bold")
        text.set_fontsize(12)
    plt.subplots_adjust(left=0.15)  # Agregar espacio a la izquierda
    plt.savefig(path + '/rose.jpg', dpi=200, bbox_inches='tight')
    # function to label percents over bars
    def addlabels(x,y):
        for i in range(len(x)):
            plt.text(i, y[i]+0.5, str(y[i])+'%', ha = 'center', fontweight='bold', color='k')
        
    fig = plt.figure(figsize=(9, 9))        
    #Veliocity histogram  + accumulated percent
    ax0 = plt.subplot2grid((2, 1), (0, 0), colspan=1)
    ws_freq = np.sum(table, axis=1)
    ax0.bar(np.arange(len(vel_bins)-1), ws_freq, align='center', color='c', edgecolor='k', zorder=3)
    
    #round to 2 decimals for labels on top of bars
    WS = np.zeros(len(ws_freq))    
    for j in range(len(ws_freq)):
        WS[j]=np.round(ws_freq[j], 2)
        
    #histogram bin labels for x axis
    xlabels=[]
    for j in range(len(vel_bins)-1):
        if j<len(vel_bins)-1:
            xlabels.append('['+str(round(vel_bins[j],1))+','+str(round(vel_bins[j+1],1))+'(')
        else:
            xlabels.append('['+str(round(vel_bins[j],1))+','+str(round(vel_bins[j+1],1))+']')   
    
    xticks=np.arange(len(vel_bins)-1)
    plt.gca().set_xticks(xticks)
    plt.gca().set_xticklabels(xlabels, color='k')
    ax0.yaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))   
    addlabels(np.arange(len(vel_bins)-1), WS)
    ax0.set_xlabel("Velocidad del viento [m/s]", fontsize=13)
    ax0.set_ylabel("Porcentaje del total de datos", fontsize=13)
    ax0.set_title("Histograma de velocidad del viento", fontweight='bold',fontsize=14)
    ax0.grid(zorder=0)
    plt.margins(x=0.05)
    
    #Accumulated percent
    accumulate = np.zeros(len(table)+1)
    for j in range(1,len(table)+1):
        accumulate[j] = accumulate[j-1]+sum(table[j-1])
    
    accumulate = accumulate[1:]
    ax1 = ax0.twinx()
    ax1.plot(np.arange(len(accumulate)),accumulate,'r')
    ax1.yaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
    ax1.tick_params(axis='y', colors='red')
    plt.ylabel("Porcentaje acumulado", color='r',fontweight='bold', fontsize=13)
    
    ax2 = plt.subplot2grid((2, 1), (1, 0), colspan=1)
    wd_freq = np.sum(table, axis=0)
    #decimales
    WD = np.zeros(len(wd_freq))    
    for j in range(len(wd_freq)):
        WD[j]=np.round(wd_freq[j], 2)    
    ax2.bar(np.arange(8), wd_freq, align='center', color='greenyellow', edgecolor='k',zorder=3)
    xlabels = ('N','N-E','E','S-E','S','S-O','O','N-O')
    xticks=np.arange(8)
    plt.gca().set_xticks(xticks)
    plt.gca().set_xticklabels(xlabels, color='k')
    addlabels(np.arange(8), WD)
    plt.xlabel("Dirección del viento", fontsize=13)
    plt.ylabel("Porcentaje del total de datos", fontsize=13)
    ax2.yaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
    plt.title("Histograma de dirección del viento", fontweight='bold',  fontsize=14)
    plt.grid(zorder=0) #poner grilla como promera capa. 
    plt.margins(x=0.05)
    
    plt.tight_layout()
    plt.savefig(path+'/2-Histogramas.jpg',dpi=200)
    
    # ===============================
    # Histograma individual de velocidad + acumulado
    # ===============================
    fig_vel = plt.figure(figsize=(9, 4))
    ax_vel = fig_vel.add_subplot(111)

    # Frecuencia por bin de velocidad
    ws_freq = np.sum(table, axis=1)

    ax_vel.bar(
        np.arange(len(vel_bins)-1),
        ws_freq,
        align='center',
        color='c',
        edgecolor='k',
        zorder=3
    )

    # Etiquetas de bins
    xlabels = []
    for j in range(len(vel_bins)-1):
        xlabels.append(f"[{vel_bins[j]:.1f},{vel_bins[j+1]:.1f})")

    ax_vel.set_xticks(np.arange(len(vel_bins)-1))
    ax_vel.set_xticklabels(xlabels)

    ax_vel.yaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
    ax_vel.set_xlabel("Velocidad del viento [m/s]", fontsize=12)
    ax_vel.set_ylabel("Porcentaje del total de datos", fontsize=12)
    ax_vel.set_title("Histograma de velocidad del viento", fontweight='bold')

    ax_vel.grid(zorder=0)
    plt.margins(x=0.05)

    # -------------------------------
    # Porcentaje acumulado (mismo criterio que el subplot)
    # -------------------------------
    accumulate = np.zeros(len(table)+1)
    for j in range(1, len(table)+1):
        accumulate[j] = accumulate[j-1] + np.sum(table[j-1])

    accumulate = accumulate[1:]

    ax_acc = ax_vel.twinx()
    ax_acc.plot(
        np.arange(len(accumulate)),
        accumulate,
        'r'
    )
    ax_acc.yaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
    ax_acc.tick_params(axis='y', colors='red')
    ax_acc.set_ylabel(
        "Porcentaje acumulado",
        color='r',
        fontweight='bold',
        fontsize=12
    )

    plt.tight_layout()
    plt.savefig(path + '/vel_hist.jpg', dpi=200)
    plt.close(fig_vel)


    # ===============================
    # Histograma individual de dirección
    # ===============================
    fig_dir = plt.figure(figsize=(9, 4))
    ax_dir = fig_dir.add_subplot(111)

    wd_freq = np.sum(table, axis=0)

    ax_dir.bar(
        np.arange(8),
        wd_freq,
        align='center',
        color='greenyellow',
        edgecolor='k',
        zorder=3
    )

    xlabels = ('N','N-E','E','S-E','S','S-O','O','N-O')
    ax_dir.set_xticks(np.arange(8))
    ax_dir.set_xticklabels(xlabels)

    ax_dir.yaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
    ax_dir.set_xlabel("Dirección del viento", fontsize=12)
    ax_dir.set_ylabel("Porcentaje del total de datos", fontsize=12)
    ax_dir.set_title("Histograma de dirección del viento", fontweight='bold')

    ax_dir.grid(zorder=0)
    plt.tight_layout()
    plt.savefig(path + '/dir_hist.jpg', dpi=200)
    plt.close(fig_dir)


    # ===============================
    # Serie de tiempo magnitud
    # ===============================
    
    fig = plt.figure(figsize = (15, 5))
    plt.plot(df.index,df.WS_max, c='r', label='Ráfagas')
    plt.plot(df.index,df.WS, c='k',label='Velocidad')
    plt.legend()
    plt.ylabel('Velocidad de viento [m/s]')
    plt.title('Magnitud del viento', fontsize=14, fontweight='bold')
    plt.grid()
    plt.margins(x=0)
    plt.tight_layout()
    plt.savefig(path+'/3-Serie_tiempo_magnitud.jpg',dpi=200)

    u,v = WINDdm2uv(df.WD, df.WS)
    df.insert(0,'u',u)
    df.insert(1,'v',v)
    
    hourly_mean_u = np.zeros(24)
    hourly_mean_v = np.zeros(24)
    hourly_mean = np.zeros(24)
    
    for i in range(24):
        dfh = df[df.index.hour == i]
        hourly_mean_u[i] = np.nanmean(dfh.u)
        hourly_mean_v[i] = np.nanmean(dfh.v)
        hourly_mean[i] = np.nanmean(dfh.WS)

    plt.figure(figsize=(12,4))
    plt.plot(hourly_mean, linestyle='-', marker='o',label = 'promedio')
    plt.xticks(np.arange(24))
    plt.yticks(np.arange(math.floor(min(hourly_mean)), math.ceil(max(hourly_mean)),0.5))
    plt.xlabel('Hora', fontsize=13)
    plt.ylabel('Velocidad promedio [m/s]', fontsize=13)
    plt.title('Perfil diario del viento', fontweight='bold')
    plt.grid()
    plt.autoscale(enable=True, axis='x', tight=True)
    plt.tight_layout()
    plt.savefig(path+'/4-Perfil_diario.jpg',dpi=200)
        
    plt.figure(figsize=(12,4))
    plt.plot(hourly_mean, color = 'k', linestyle='-', marker='o',label = 'Magnitud Promedio')
    plt.plot(hourly_mean_u, color = 'b', linestyle='-', marker='o',label = 'Componente U')
    plt.plot(hourly_mean_v, color = 'r', linestyle='-', marker='o',label = 'Componente V')
    plt.xticks(np.arange(24))
    if  min(hourly_mean_u) < min(hourly_mean_v):
        plt.yticks(np.arange(math.floor(min(hourly_mean_u)), math.ceil(max(hourly_mean))+1,1))
    else:
        plt.yticks(np.arange(math.floor(min(hourly_mean_v)), math.ceil(max(hourly_mean))+1,1))
    plt.xlabel('Hora', fontsize=13)
    plt.ylabel('Velocidad promedio [m/s]', fontsize=13)
    plt.title('Perfil diario del la velocidad y los componentes ortogonales', fontweight='bold')
    plt.grid()
    plt.legend(loc='lower left')
    plt.autoscale(enable=True, axis='x', tight=True)
    plt.tight_layout()
    plt.savefig(path+'/4-Perfil_diario_UV.jpg',dpi=200)

    fig = plt.figure(figsize = (15, 5))
    plt.plot(df.index,df.u, c='b',label='Componente U (Este-Oeste)',alpha=0.5)
    plt.plot(df.index,df.v, c='r',label='Componente V (Norte-Sur)', alpha=0.5,zorder=0)
    plt.ylabel('Velocidad de viento [m/s]')
    plt.title('Analisis de Componentes Ortogonales', fontsize=14, fontweight='bold')
    plt.legend()
    plt.grid()
    plt.margins(x=0)
    plt.tight_layout()
    plt.savefig(path+'/5-Serie_tiempo_ortogonales.jpg',dpi=200)

    hora=np.arange(0,25,4)
    vel_bins_rose = vel_bins[:-1]
    #histogram bin labels fo x axis
    xlabelsV=[]
    for j in range(len(vel_bins)-1):
        if j<len(vel_bins)-2:
            xlabelsV.append('['+str(np.round(vel_bins[j],1))+','+str(np.round(vel_bins[j+1],1))+'(')
        else:
            xlabelsV.append('['+str(np.round(vel_bins[j],1))+','+str(np.round(vel_bins[j+1],1))+']')  
    xlabelsD = ('N','NE','E','SE','S','SO','O','NO')
    
    # función para etiquetar con procentajes
    def addlabels(x,y):
        for i in range(len(x)):
            plt.text(i, y[i]+0.5, str(y[i])+'%', ha = 'center', fontweight='bold', color='k')
    
    for i in range(len(hora)-1):
        DF = df[(df.index.hour==hora[i]) & (df.index.hour<hora[i+1])]
        wd = DF.WD
        ws = DF.WS
        fig = plt.figure(figsize=(4, 4))
        ax = plt.subplot2grid((1, 1), (0, 0),projection='windrose')
        ax.bar(wd, ws, normed=True, blowto=False, nsector=8, opening=1, bins=vel_bins[:-1], cmap=cm, edgecolor='white')
        table0 = ax._info['table']
        fig = plt.figure(figsize=(17, 17))
        ax0 = plt.subplot2grid((3, 2), (0, 0), colspan=2)
        ax0.plot(df.index,df.WS, color='k',zorder=0,label='Registo completo de viento')
        ax0.scatter(DF.index, ws, color='c',zorder=1,label='Regístro Hora '+str(hora[i]))
        ax0.grid()
        ax0.legend()
        plt.ylabel('Velocidad de viento [m/s]')
        plt.margins(x=0)
        plt.tight_layout()
        plt.title('Análisis de viento Hora '+str(hora[i]), fontsize=14, fontweight='bold')
    
        ax1 = plt.subplot2grid((3, 2), (1, 0), colspan=1,projection='windrose')
        cm = plt.get_cmap('jet')
        ax1.bar(wd, ws, normed=True, blowto=False, nsector=8, opening=1, bins=vel_bins[:-1], cmap=cm, edgecolor='white')
        ax1.yaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
        ax1.set_xticklabels(['E','NE','N','NO','O','SO','S','SE'], fontweight='bold', fontsize=12)  
        ax1.set_legend(loc='best', fontsize=13)
        ax1.set_legend(bbox_to_anchor=(-0.2, 0.5),loc='center')
        ax1.set_rlabel_position(0)  
        ax1.set_title('Rosa de Viento',fontweight='bold',pad=20)  
        #generate with windrose but I'll use this in the histograms
        table = ax1._info['table']
    
        ax2 = plt.subplot2grid((3, 2), (1, 1), colspan=1, projection='polar')
        wd_radians = [math.radians(j) for j in wd] #the same as #wd_radians = [i/180*np.pi for i in  wd]
        ax2.scatter(wd_radians,ws, s=50, c ='yellow', edgecolor='k')
        k = max(enumerate(ws), key = lambda x: x[1])[0] 
        ax2.scatter(wd_radians[k], ws[k],s=80, c ='r', edgecolor='k')
        ax2.set_theta_zero_location('N')
        ax2.set_theta_direction(-1)
        ax2.set_xticklabels(['N','NE','E','SE','S','SO','O','NO'], fontweight='bold', fontsize=12)  
        ax2.set_rlabel_position(90)  
        ax2.set_title("Diagrama polar de dispersión", fontweight='bold',pad=20)  
        label_position=ax2.get_rlabel_position()
        ax2.text(np.radians(label_position+5),ax2.get_rmax()/2,'Velocidad[m/s]',fontweight='bold', fontsize=12,
                rotation=0,ha='center',va='center')
        
        ax3 = plt.subplot2grid((3, 2), (2, 0), colspan=1)
        #Veliocity histogram  + accumulated percent
        ws_freq = np.sum(table, axis=1)
        ax3.bar(np.arange(len(vel_bins)-1), ws_freq, align='center', color='c', edgecolor='k', zorder=3)
        #round to 2 decimals for labels on top of bars
        WS = np.zeros(len(ws_freq))    
        for j in range(len(ws_freq)):
            WS[j]=np.round(ws_freq[j], 2)
    
        xticks=np.arange(len(vel_bins)-1)
        plt.gca().set_xticks(xticks)
        plt.gca().set_xticklabels(xlabelsV,  fontweight='bold', color='k')
        ax3.yaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
        addlabels(np.arange(len(vel_bins)-1), WS)
        ax3.set_xlabel("Velocidad del viento [m/s]")
        ax3.set_ylabel("Porcentaje del total de datos")
        ax3.set_title("Histograma de velocidad del viento", fontweight='bold',  fontsize=14)
        ax3.grid(zorder=0)
        ax3.margins(x=0.05)
        #Accumulated percent
        accumulate = np.zeros(len(table)+1)
        for j in range(1,len(table)+1):
            accumulate[j] = accumulate[j-1]+sum(table0[j-1])
        accumulate = accumulate[1:]
        ax4 = ax3.twinx()
        ax4.plot(np.arange(len(accumulate)),accumulate[:],'r')#this line is different for some reason
        ax4.yaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
        ax4.tick_params(axis='y', colors='red')
        ax4.margins(x=0.05)
        plt.ylabel("Porcentaje acumulado", color='r')
    
        ax5 = plt.subplot2grid((3, 2), (2, 1), colspan=1)
        wd_freq = np.sum(table, axis=0)
        #decimales
        WD = np.zeros(len(wd_freq))    
        for j in range(len(wd_freq)):
            WD[j]=np.round(wd_freq[j], 2)    
        ax5.bar(np.arange(8), wd_freq, align='center', color='greenyellow', edgecolor='k',zorder=3)
        xticks=np.arange(8)
        plt.gca().set_xticks(xticks)
        plt.gca().set_xticklabels(xlabelsD, color='k')
        ax5.yaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
        addlabels(np.arange(8), WD)
        plt.xlabel("Dirección del viento [°]")
        plt.ylabel("Porcentaje del total de datos")
        plt.title("Histograma de dirección del viento", fontweight='bold',  fontsize=14)
        plt.grid(zorder=0) #poner grilla como promera capa. 
        plt.margins(x=0.05)
        plt.tight_layout()
        
        plt.savefig(path+'/Análisis_horario_viento - '+str(hora[i])+'.jpg',dpi=400)

def spectral_density_figure(df,path, dt=1/6):
    import scipy.stats as ss
    import matplotlib.pyplot as plt

    interpolate(df)
    freqsU, psU, psdU, dof = spectrum2(df.u, dt=dt)
    freqsV, psV, psdV, dof = spectrum2(df.v, dt=dt)

    plt.figure(figsize = (11, 4))
    FREQ = [1/24,1/12,1/8,1/6,1/3]   #1,2,3,4, 
    plt.vlines(FREQ,0.0001,100000, color='lime')
    plt.loglog(freqsU, psdU, 'b', alpha=0.5, label='Componente U (Este-Oeste)')
    plt.loglog(freqsV, psdV, 'r', alpha=0.5, label='Componente V (Norte-Sur)')
    plt.title('Analisis espectral de componentes ortogonales', fontsize=14, fontweight='bold')
    plt.ylabel('Densidad espectral [$m^2/s^2$/cph]',fontsize=14)
    plt.xlabel('Frecuencia [cph]',fontsize=14)
    plt.legend(loc = 'lower left')
    XTICKS = [24,12,8,6,3]
    plt.xticks(FREQ, labels=XTICKS)

    plt.grid(True, which="both")

    LEFT = 0.005
    RIGHT = 4
    BOTTOM = 0.001
    
    if min(psdU) < min(psdV):
        psdMIN = psdU
    elif min(psdV) < min(psdU):
        psdMIN = psdV
    if (min(psdMIN) > 0.001) and (min(psdMIN) < 0.01):
        BOTTOM = 0.0009
    elif (min(psdMIN) > 0.0001) and (min(psdMIN) < 0.001):
        BOTTOM = 0.00009
    elif (min(psdMIN) > 0.00001) and (min(psdMIN) < 0.0001):
        BOTTOM = 0.000009
    
    if max(psdU) > max(psdV):
        psdMAX = psdU
    elif max(psdV) > max(psdU):
        psdMAX = psdV
    if max(psdMAX) <= 1:
        TOP = 2
    elif (max(psdMAX) > 1) and (max(psdMAX) < 10):
        TOP = 30
    elif (max(psdMAX) > 10) and (max(psdMAX) < 100):
        TOP = 300
    elif (max(psdMAX) > 100) and (max(psdMAX) < 1000):
        TOP = 3000
    elif (max(psdMAX) > 1000) and (max(psdMAX) < 10000):
        TOP = 30000
    elif (max(psdMAX) > 10000) and (max(psdMAX) < 100000):
        TOP = 300000
        
    # location of confidence limit bar
    conf_x = 1.2/24
    conf_y0 = 80
    conf = conf_y0 * dof / ss.chi2.ppf([0.025, 0.975], dof)
    plt.plot([conf_x, conf_x], conf,color='k', lw=1.5)
    plt.plot(conf_x, conf_y0, color='k', ls='none', 
    marker='_', ms=8, mew=2)
    plt.xlim(left=LEFT, right=RIGHT)
    plt.ylim(bottom=BOTTOM, top=TOP)
    #conf = conf_y0 * dof / ss.chi2.ppf([0.95], dof)
    #ax[p].errorbar(x=conf_x, y=conf_y0, yerr=conf, fmt='o', color='k')
    plt.text(1.6/24,conf_y0,'IC = 95% con GL = '+str(dof), fontsize=14)
    plt.tight_layout()
    plt.savefig(path+'/6-Análisis_espectral_cph.jpg',dpi=400)
    #plt.close()
    

def spectrum1(h, dt=1/6):
    """
    First cut at spectral estimation: very crude.
    Returns frequencies, power spectrum, and
    power spectral density.
    Only positive frequencies between (and not including)
    zero and the Nyquist are output.
    """
    import numpy as np
    nt = len(h)
    npositive = nt//2
    pslice = slice(1, npositive)
    freqs = np.fft.fftfreq(nt, d=dt)[pslice] 
    ft = np.fft.fft(h)[pslice]
    psraw = np.abs(ft) ** 2
    # Double to account for the energy in the negative frequencies.
    psraw *= 2
    # Normalization for Power Spectrum
    psraw /= nt**2
    # Convert PS to Power Spectral Density
    psdraw = psraw * dt * nt  # nt * dt is record length
    return freqs, psraw, psdraw

def spectrum2(h, dt=1/6, nsmooth=10):
    """
    Add simple boxcar smoothing to the raw periodogram.
    Chop off the ends to avoid end effects.
    """
    import numpy as np
    freqs, ps, psd = spectrum1(h, dt=dt)
    weights = np.ones(nsmooth, dtype=float) / nsmooth
    ps_s = np.convolve(ps, weights, mode='valid')
    psd_s = np.convolve(psd, weights, mode='valid')
    freqs_s = np.convolve(freqs, weights, mode='valid') #convert to cycles per day
    dof = nsmooth*2
    return freqs_s, ps_s, psd_s, dof

def interpolate(df):
    import math
    import pandas as pd
    import numpy as np
    #find where gaps start and finish
    for i in range(df.shape[1]):
    # for i in range(df.select_dtypes(include=[float, int]).shape[1]): MODIFICACION POR TV PARA VIENTOS GUAMBLAD POR LA MANIPULACION QUE SE LE HIZO A ESOS DATOS
        x0 = []
        x1 = []
        y0 = []
        y1 = []
        for j in range(df.shape[0]):
            if math.isnan(df.iloc[j,i])==True and math.isfinite(df.iloc[j-1,i])==True:
                x0.append(j-1)
                y0.append(df.iloc[j-1,i])
            if math.isnan(df.iloc[j,i])==True and math.isfinite(df.iloc[j+1,i])==True:
                x1.append(j+1)
                y1.append(df.iloc[j+1,i])
        #fill in gaps
        if len(x0)>0:
            for k in range(len(x0)):
                for l in range(x1[k]-x0[k]-1):
                    df.iloc[x0[k]+1+l,i] = y0[k]+(y1[k]-y0[k])/(x1[k]-x0[k])*(x0[k]+1+l-x0[k])

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
    
def wind_report_monthly_figures(path, df,vel_bins):
    import numpy as np
    import matplotlib.pyplot as plt
    import matplotlib.ticker as mtick
    from windrose import WindroseAxes
    import math

    meses, año, monthyear_labels = monthlabels(df)
    vel_bins_rose = vel_bins[:-1] 
    #histogram bin labels for x axis
    xlabelsV=[]
    for j in range(len(vel_bins)-1):
        if j<len(vel_bins)-1:
            xlabelsV.append('['+str(np.round(vel_bins[j],1))+','+str(np.round(vel_bins[j+1],1))+'(')
        else:
            xlabelsV.append('['+str(np.round(vel_bins[j],1))+','+str(np.round(vel_bins[j+1],1))+']')  
    xlabelsD = ('N','NE','E','SE','S','SO','O','NO') 
    # función para etiquetar con procentajes
    def addlabels(x,y):
        for i in range(len(x)):
            plt.text(i, y[i]+0.5, str(y[i])+'%', ha = 'center', fontweight='bold', color='k')
    
    for i in range(len(meses)):
        DF = df[(df.index.month==meses[i]) & (df.index.year==año[i])]
        wd = DF.WD
        ws = DF.WS
    
        fig = plt.figure(figsize=(17, 17))
        ax0 = plt.subplot2grid((3, 2), (0, 0), colspan=2)
        ax0.plot(DF.index,ws, color='k',zorder=0,label='Registo del mes')
        ax0.grid()
        ax0.legend()
        plt.ylabel('Velocidad de viento [m/s]')
        plt.title('Análisis de viento '+str(monthyear_labels[i]), fontsize=14, fontweight='bold')
        plt.margins(x=0)
        plt.tight_layout()
    
        ax1 = plt.subplot2grid((3, 2), (1, 0), colspan=1,projection='windrose')
        cm = plt.get_cmap('jet')
        ax1.bar(wd, ws, normed=True, blowto=False, nsector=8, opening=1, bins=vel_bins_rose, cmap=cm, edgecolor='white')
        ax1.yaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
        ax1.set_xticklabels(['E','NE','N','NO','O','SO','S','SE'], fontweight='bold', fontsize=12)  
        ax1.set_legend(loc='best', fontsize=13)
        ax1.set_legend(bbox_to_anchor=(-0.2, 0.5),loc='center')
        ax1.set_rlabel_position(0)  
        ax1.set_title('Rosa de Viento',fontweight='bold',pad=20)  
        #generate with windrose but I'll use this in the histograms
        table = ax1._info['table']
    
        ax2 = plt.subplot2grid((3, 2), (1, 1), colspan=1, projection='polar')
        wd_radians = [math.radians(j) for j in wd] #the same as #wd_radians = [i/180*np.pi for i in  wd]
        ax2.scatter(wd_radians,ws, s=50, c ='yellow', edgecolor='k')
        k = max(enumerate(ws), key = lambda x: x[1])[0] 
        ax2.scatter(wd_radians[k], ws[k],s=80, c ='r', edgecolor='k')
        ax2.set_theta_zero_location('N')
        ax2.set_theta_direction(-1)
        ax2.set_xticklabels(['N','NE','E','SE','S','SO','O','NO'], fontweight='bold', fontsize=12)  
        ax2.set_rlabel_position(90)  
        ax2.set_rmax(math.ceil(max(df.WS)))
        ax2.set_title("Diagrama polar de dispersión", fontweight='bold',pad=20)  
        label_position=ax2.get_rlabel_position()
        ax2.text(np.radians(label_position+5),ax2.get_rmax()/2,'Velocidad[m/s]',fontweight='bold', fontsize=12,
                rotation=0,ha='center',va='center')
    
        ax3 = plt.subplot2grid((3, 2), (2, 0), colspan=1)
        #Veliocity histogram  + accumulated percent
        ws_freq = np.sum(table, axis=1)
        ax3.bar(np.arange(len(vel_bins)-1), ws_freq, align='center', color='c', edgecolor='k', zorder=3)
        #round to 2 decimals for labels on top of bars
        WS = np.zeros(len(ws_freq))    
        for j in range(len(ws_freq)):
            WS[j]=np.round(ws_freq[j], 2)

        xticks=np.arange(len(vel_bins)-1)
        plt.gca().set_xticks(xticks)
        plt.gca().set_xticklabels(xlabelsV,  fontweight='bold', color='k')
        ax3.yaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
        addlabels(np.arange(len(vel_bins)-1), WS)
        ax3.set_xlabel("Velocidad del viento [m/s]")
        ax3.set_ylabel("Porcentaje del total de datos")
        ax3.set_title("Histograma de velocidad del viento", fontweight='bold',  fontsize=14)
        ax3.grid(zorder=0)
        ax3.margins(x=0.05)
        #Accumulated percent
        accumulate = np.zeros(len(table)+1)
        for j in range(1,len(table)+1):
            accumulate[j] = accumulate[j-1]+sum(table[j-1])
        accumulate = accumulate[1:]
        ax4 = ax3.twinx()
        ax4.plot(np.arange(len(accumulate)),accumulate[:],'r')#this line is different for some reason
        ax4.yaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
        ax4.tick_params(axis='y', colors='red')
        ax4.margins(x=0.05)
        plt.ylabel("Porcentaje acumulado", color='r')
    
        ax5 = plt.subplot2grid((3, 2), (2, 1), colspan=1)
        wd_freq = np.sum(table, axis=0)
        #decimales
        WD = np.zeros(len(wd_freq))    
        for j in range(len(wd_freq)):
            WD[j]=np.round(wd_freq[j], 2)    
    
        ax5.bar(np.arange(8), wd_freq, align='center', color='greenyellow', edgecolor='k',zorder=3)
        xticks=np.arange(8)
        plt.gca().set_xticks(xticks)
        plt.gca().set_xticklabels(xlabelsD, color='k')
        ax5.yaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
        addlabels(np.arange(8), WD)
        plt.xlabel("Dirección del viento [°]")
        plt.ylabel("Porcentaje del total de datos")
        plt.title("Histograma de dirección del viento", fontweight='bold',  fontsize=14)
        plt.grid(zorder=0) #poner grilla como promera capa. 
        plt.margins(x=0.05)
        plt.tight_layout()
        plt.savefig(path+'/Análisis_mensual_viento - '+str(año[i])+'-'+str(meses[i])+'.jpg',dpi=400)
    
def wind_year_figures(path,df,XLABELS,MAX,MEAN,P5,P95,vel_bins):
    import numpy as np
    import matplotlib.pyplot as plt
    import matplotlib.ticker as mtick
    from windrose import WindroseAxes
    import matplotlib as mpl
    from matplotlib.cm import ScalarMappable
    from matplotlib import cm,colors
    import math
    from .DMUV import WINDdm2uv

    meses, año, monthyear_labels = monthlabels(df)
    vel_bins_rose = vel_bins[:-1]
    #histogram bin labels for x axis
    xlabelsV=[]
    for j in range(len(vel_bins)-1):
        if j<len(vel_bins)-1:
            xlabelsV.append('['+str(np.round(vel_bins[j],1))+','+str(np.round(vel_bins[j+1],1))+'(')
        else:
            xlabelsV.append('['+str(np.round(vel_bins[j],1))+','+str(np.round(vel_bins[j+1],1))+']')  
    xlabelsD = ('N','NE','E','SE','S','SO','O','NO')
    
    # función para etiquetar con procentajes
    def addlabels(x,y):
        for i in range(len(x)):
            plt.text(i, y[i]+0.5, str(y[i])+'%', ha = 'center', fontweight='bold', color='k')
    
    for i in range(len(meses)):
        DF = df[(df.index.month==meses[i]) & (df.index.year==año[i])]
        wd = DF.WD
        ws = DF.WS
    
        fig = plt.figure(figsize=(17, 17))
    
        ax0 = plt.subplot2grid((3, 2), (0, 0), colspan=2)
        ax0.plot(DF.index,ws, color='k',zorder=0,label='Registo del mes')
        ax0.grid()
        ax0.legend()
        plt.ylabel('Velocidad de viento [m/s]')
        plt.title('Análisis de viento '+str(monthyear_labels[i]), fontsize=14, fontweight='bold')
        plt.margins(x=0)
        plt.tight_layout()
    
        ax1 = plt.subplot2grid((3, 2), (1, 0), colspan=1,projection='windrose')
        cm = plt.get_cmap('jet')
        ax1.bar(wd, ws, normed=True, blowto=False, nsector=8, opening=1, bins=vel_bins_rose, cmap=cm, edgecolor='white')
        ax1.yaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
        ax1.set_xticklabels(['E','NE','N','NO','O','SO','S','SE'], fontweight='bold', fontsize=12)  
        ax1.set_legend(loc='best', fontsize=13)
        ax1.set_legend(bbox_to_anchor=(-0.2, 0.5),loc='center')
        ax1.set_rlabel_position(0)  
        ax1.set_title('Rosa de Viento',fontweight='bold',pad=20)  
        #generate with windrose but I'll use this in the histograms
        table = ax1._info['table']
    
        ax2 = plt.subplot2grid((3, 2), (1, 1), colspan=1, projection='polar')
        wd_radians = [math.radians(j) for j in wd] #the same as #wd_radians = [i/180*np.pi for i in  wd]
        ax2.scatter(wd_radians,ws, s=50, c ='yellow', edgecolor='k')
        k = max(enumerate(ws), key = lambda x: x[1])[0] 
        ax2.scatter(wd_radians[k], ws[k],s=80, c ='r', edgecolor='k')
        ax2.set_theta_zero_location('N')
        ax2.set_theta_direction(-1)
        ax2.set_xticklabels(['N','NE','E','SE','S','SO','O','NO'], fontweight='bold', fontsize=12)  
        ax2.set_rlabel_position(90)  
        ax2.set_rmax(math.ceil(max(df.WS)))
        ax2.set_title("Diagrama polar de dispersión", fontweight='bold',pad=20)  
        label_position=ax2.get_rlabel_position()
        ax2.text(np.radians(label_position+5),ax2.get_rmax()/2,'Velocidad[m/s]',fontweight='bold', fontsize=12,
                rotation=0,ha='center',va='center')
    
        ax3 = plt.subplot2grid((3, 2), (2, 0), colspan=1)
        #Veliocity histogram  + accumulated percent
        ws_freq = np.sum(table, axis=1)
        ax3.bar(np.arange(len(vel_bins)-1), ws_freq, align='center', color='c', edgecolor='k', zorder=3)
        #round to 2 decimals for labels on top of bars
        WS = np.zeros(len(ws_freq))    
        for j in range(len(ws_freq)):
            WS[j]=np.round(ws_freq[j], 2)
    
        xticks=np.arange(len(vel_bins)-1)
        plt.gca().set_xticks(xticks)
        plt.gca().set_xticklabels(xlabelsV,  fontweight='bold', color='k')
        ax3.yaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
        addlabels(np.arange(len(vel_bins)-1), WS)
        ax3.set_xlabel("Velocidad del viento [m/s]")
        ax3.set_ylabel("Porcentaje del total de datos")
        ax3.set_title("Histograma de velocidad del viento", fontweight='bold',  fontsize=14)
        ax3.grid(zorder=0)
        ax3.margins(x=0.05)
        #Accumulated percent
        accumulate = np.zeros(len(table)+1)
        for j in range(1,len(table)+1):
            accumulate[j] = accumulate[j-1]+sum(table[j-1])
        accumulate = accumulate[1:]
        ax4 = ax3.twinx()
        ax4.plot(np.arange(len(accumulate)),accumulate[:],'r')#this line is different for some reason
        ax4.yaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
        ax4.tick_params(axis='y', colors='red')
        ax4.margins(x=0.05)
    
        plt.ylabel("Porcentaje acumulado", color='r')
    
        ax5 = plt.subplot2grid((3, 2), (2, 1), colspan=1)
        wd_freq = np.sum(table, axis=0)
        #decimales
        WD = np.zeros(len(wd_freq))    
        for j in range(len(wd_freq)):
            WD[j]=np.round(wd_freq[j], 2)    
    
        ax5.bar(np.arange(8), wd_freq, align='center', color='greenyellow', edgecolor='k',zorder=3)
        xticks=np.arange(8)
        plt.gca().set_xticks(xticks)
        plt.gca().set_xticklabels(xlabelsD, color='k')
        ax5.yaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
        addlabels(np.arange(8), WD)
        plt.xlabel("Dirección del viento [°]")
        plt.ylabel("Porcentaje del total de datos")
        plt.title("Histograma de dirección del viento", fontweight='bold',  fontsize=14)
        plt.grid(zorder=0) #poner grilla como promera capa. 
        plt.margins(x=0.05)
        plt.tight_layout()
        
        plt.savefig(path+'/Análisis_mensual_viento - '+str(año[i])+'-'+str(meses[i])+'.jpg',dpi=400)
        
    plt.figure(figsize=(14,5))
    X = np.arange(0,len(meses))
    plt.fill_between(X,P5,P95,color='tomato',alpha=0.5, ec='k',lw=2,label='90% del registro')
    plt.hlines(np.mean(df.WS),X[0],X[len(X)-1], color='c', ls='--', lw=2,label='Promedio Registro ('+str(np.round(np.mean(df.WS),1))+' m/s)')
    plt.plot(X,MEAN,ls='-',marker='o', c='b',label='Promedio Mensual [m/s]')
    for i in range(len(X)):
        plt.text(X[i], MEAN[i]+0.5, str(np.round(MEAN[i],2)), ha = 'center', fontweight='bold', color='b')
    plt.plot(X,MAX,ls='',marker='x', c='k',label='Máximo Mensual [m/s]')
    for i in range(len(X)):
        plt.text(X[i], MAX[i]+0.5, str(np.round(MAX[i],2)), ha = 'center', fontweight='bold', color='k')
    plt.xticks(X, labels=XLABELS)
    plt.ylim(-0.1,max(MAX)+3)
    plt.title('Ciclo Anual de la Velocidad del Viento', fontweight='bold')
    plt.ylabel('Velodidad del viento [m/s]')
    #plt.legend(loc='upper left', bbox_to_anchor=(0.1, 0.5, 0.5, 0.5))
    plt.legend(loc='upper right')
    plt.grid()
    plt.autoscale(enable=True, axis='x',tight=True)
    plt.tight_layout()
    plt.savefig(path+'/4-Perfil-Anual-Viento.jpg',dpi=200)
    
    U,V = WINDdm2uv(df.WD,df.WS)
    #df.insert(3,'U',U)
    #df.insert(4,'V',V)

    VEL_hourly_mean_month = np.zeros((len(meses),24))
    DIR_hourly_mean_month = np.zeros((len(meses),24))
    
    hourly_mean = np.zeros(24)
    for h in range(24):
        dfh = df[df.index.hour == h]
        hourly_mean[h] = np.nanmean(dfh.WS)
    
    horas=np.arange(24)
    cbar_ticks=np.zeros(8)
    for i in range(8):
        cbar_ticks[i] = 45*i
        
    VEL_hourly_mean_month = np.zeros((len(meses),24))
    DIR_hourly_mean_month = np.zeros((len(meses),24))
    
    for i in range(len(meses)):
        DF = df[(df.index.month==meses[i]) & (df.index.year==año[i])] #Filter data from a particular month  
        #DF = df1[(df1.index.month==meses[i]) & (df1.index.year==año[i])] #Filter data from a particular month  
        for h in range(24):
            #dfh0 = DF0[DF0.index.hour == h]
            dfh = DF[DF.index.hour == h]
            VEL_hourly_mean_month[i,h] = np.nanmean(dfh.WS)
            u = np.nanmean(dfh.u)
            v = np.nanmean(dfh.v)
            if  u>0.000000001 and v<0: #2nd quadrant
                DIR_hourly_mean_month[i,h] =  math.atan(u/v)*180/math.pi+360
            elif v>=0: #1st and 4th quadrant
                DIR_hourly_mean_month[i,h] =  math.atan(u/v)*180/math.pi+180
            else: #3rd quadrant
                DIR_hourly_mean_month[i,h] =  math.atan(u/v)*180/math.pi
    
    from matplotlib.pyplot import cm
    n =int(np.ceil(len(meses)/2))
    color = iter(cm.rainbow_r(np.linspace(0, 1, n)))
    
    fig = plt.figure(figsize=(15.2, 16),layout='constrained')
    ax0 = plt.subplot2grid((5, 2), (0, 0), colspan=2)  
    ax1 = plt.subplot2grid((5, 2), (1, 0), colspan=2, rowspan=2)    
    ax2 = plt.subplot2grid((5, 2), (3, 0), colspan=2,  rowspan=2)      
    
    for i in range(n):
        c = next(color)
        ax0.plot(np.arange(24),VEL_hourly_mean_month[i,:], c=c,ls='--',lw = 2,label = monthyear_labels[i])
    color = iter(cm.rainbow_r(np.linspace(0, 1, n)))
    for i in range(len(meses)-n):
        c = next(color)
        ax0.plot(np.arange(24),VEL_hourly_mean_month[i+n,:], c=c,ls=':',lw = 2,label = monthyear_labels[i+n])
    
    ax0.plot(np.arange(24),hourly_mean, ls='-', lw=2,marker='o',c='k',label = 'Todos los datos')    
    ax0.set_xticks(np.arange(24))
    ax0.set_ylim(np.nanmin(VEL_hourly_mean_month)-0.2, np.nanmax(VEL_hourly_mean_month[1:,:]+0.2))
    #ax0.set_xlabel('Hora', fontsize=13)
    ax0.set_ylabel('Velocidad promedio [m/s]', fontsize=13)
    ax0.set_title('Perfil diario del viento para cada mes', fontweight='bold',fontsize=16)
    ax0.grid()
    ax0.autoscale(enable=True, axis='x', tight=True)
    #ax0.tight_layout()
    ax0.legend(bbox_to_anchor=(-0.07, 1))
    
    def highlight_cell(x,y, ax=None, **kwargs):
        rect = plt.Rectangle((x-.5, y-.5), 1,1, fill=False, **kwargs)
        ax = ax or plt.gca()
        ax.add_patch(rect)
        return rect
        
    vmin = -22.5
    vmax = 360-22.5
    
    cmap1 =plt.cm.twilight_shifted
    # sequence falling in the n-th bin will be mapped to the n-th color
    boundaries1 =  np.zeros(17)
    for i in range(17):
        boundaries1[i] = -22.5+22.5*i
    norm1 = mpl.colors.BoundaryNorm(boundaries1, cmap1.N)
    CMAP1 = mpl.cm.ScalarMappable(norm=norm1, cmap=cmap1)
    
    #fig, ax = plt.subplots(2, figsize=(12,8), layout='constrained')
    
    vel = ax1.imshow(VEL_hourly_mean_month, cmap='jet',aspect = 0.9)       
    cbar = fig.colorbar(vel, ax=ax1,  format='%2.1f', pad=0.01)
    cbar.ax.set_ylabel('Velocidad [m/s]',fontsize=14)
    
    dir = ax2.imshow(DIR_hourly_mean_month, cmap=cmap1,norm=norm1,aspect = 0.9)
    cbar = fig.colorbar(CMAP1,
        ticks=cbar_ticks,
        ax=ax2,format='%2.0f', pad=0.01
    )
    for h in range(24):
        for m in range(len(meses)):
            highlight_cell(h,m,ax = ax1, color="white", linewidth=1)
    for h in range(24):
        for m in range(len(meses)):
            highlight_cell(h,m, ax = ax2, color="white", linewidth=1)
            #ax[1].text(h, m,str(int(DIR_hourly_mean_month[m,h])), ha='center',fontsize=10, fontweight='bold', color='white')
    
    cbar.ax.set_yticklabels(['N','NE','E','SE','S','SO','O','NO'])  # vertically oriented colorbar
    cbar.ax.set_ylabel('Dirección [°]',fontsize=14)
    
    ax1.set_xticks(np.arange(24))
    ax2.set_xticks(np.arange(24))
    ax1.set_yticks(np.arange(len(meses)))
    ax2.set_yticks(np.arange(len(meses)))
    
    ax1.set_xticklabels(horas)
    ax2.set_xticklabels(horas)
    ax2.set_xlabel('Hora')
    
    ax1.set_yticklabels(monthyear_labels)
    ax2.set_yticklabels(monthyear_labels)
    ax1.set_title('Velocidad [m/s]', fontweight='bold',fontsize=14)
    ax2.set_title('Dirección [°]', fontweight='bold',fontsize=14)
    
    #fig.suptitle('Perfil diario y mensual del viento', fontweight='bold', ha = 'left')
    plt.savefig(path+'/5-Perfil_diario_mensual_vel_dir_old.jpg',dpi=300,bbox_inches = "tight")


def get_octant(direction,OCTANTS):
    direction = direction % 360
    for i, oct in enumerate(OCTANTS):
        if oct['name'] == 'N':
            if direction >= oct['min'] or direction < oct['max']:
                return i
        else:
            if oct['min'] <= direction < oct['max']:
                return i
                
def calculate_octant_stats(group,OCTANTS,THRESHOLD_DOMINANT):
    import numpy as np

    if len(group) == 0:
        return []
    counts = np.zeros(8)
    speed_sums = np.zeros(8)
    for _, row in group.iterrows():
        oct_idx = get_octant(row['WD'],OCTANTS)
        counts[oct_idx] += 1
        speed_sums[oct_idx] += row['WS']
    total = len(group)
    results = []
    for i, oct in enumerate(OCTANTS):
        freq = counts[i] / total if total > 0 else 0
        avg_speed = speed_sums[i] / counts[i] if counts[i] > 0 else 0
        results.append({'name': oct['name'], 'angle': oct['angle'], 'frequency': freq, 'avg_speed': avg_speed, 'count': counts[i]})
    dominant = [r for r in results if r['frequency'] >= THRESHOLD_DOMINANT]
    dominant.sort(key=lambda x: x['frequency'], reverse=True)
    return dominant

def get_month_range(df_input):
    df_temp = df_input.copy()
    df_temp['year'] = df_temp.index.year
    df_temp['month'] = df_temp.index.month
    year_months = df_temp.groupby(['year', 'month']).size().reset_index()[['year', 'month']]
    year_months = year_months.sort_values(['year', 'month'])
    return list(zip(year_months['year'], year_months['month']))

def prepare_wind_data_for_plot(df_input, month_list,THRESHOLD_DOMINANT):
    import numpy as np
    OCTANTS = [
        {'name': 'N', 'min': 337.5, 'max': 22.5, 'angle': 0},
        {'name': 'NE', 'min': 22.5, 'max': 67.5, 'angle': 45},
        {'name': 'E', 'min': 67.5, 'max': 112.5, 'angle': 90},
        {'name': 'SE', 'min': 112.5, 'max': 157.5, 'angle': 135},
        {'name': 'S', 'min': 157.5, 'max': 202.5, 'angle': 180},
        {'name': 'SW', 'min': 202.5, 'max': 247.5, 'angle': 225},
        {'name': 'W', 'min': 247.5, 'max': 292.5, 'angle': 270},
        {'name': 'NW', 'min': 292.5, 'max': 337.5, 'angle': 315},
    ]
    df_temp = df_input.copy()
    df_temp['year'] = df_temp.index.year
    df_temp['month'] = df_temp.index.month
    df_temp['hour'] = df_temp.index.hour
    results = {}
    for idx, (year, month) in enumerate(month_list):
        for hour in range(24):
            mask = (df_temp['year'] == year) & (df_temp['month'] == month) & (df_temp['hour'] == hour)
            group = df_temp[mask]
            if len(group) > 0:
                dominant = calculate_octant_stats(group,OCTANTS,THRESHOLD_DOMINANT)
                avg_speed = group['WS'].mean()
                results[(idx, hour)] = {'dominant': dominant, 'avg_speed': avg_speed, 'count': len(group)}
            else:
                results[(idx, hour)] = {'dominant': [], 'avg_speed': np.nan, 'count': 0}
    return results

def daily_annual_cycle(df_input, title=None, save_path=None,THRESHOLD_DOMINANT = 0.25):
    
    import numpy as np
    import matplotlib.pyplot as plt
    import matplotlib.colors as mcolors
    import matplotlib.patches as mpatches
    
    ARROW_SCALE_MAX = 0.40
    ARROW_SCALE_MIN = 0.18
    ARROW_SIZE_RATIO = 0.45

    month_list = get_month_range(df_input)
    n_months = len(month_list)
    wind_data = prepare_wind_data_for_plot(df_input, month_list,THRESHOLD_DOMINANT)
    
    speed_matrix = np.zeros((n_months, 24))
    for idx in range(n_months):
        for hour in range(24):
            data = wind_data.get((idx, hour), {})
            speed_matrix[idx, hour] = data.get('avg_speed', np.nan)
    
    # Colorbar con intervalos de 0.5
    vmax = np.ceil(np.nanmax(speed_matrix) * 2) / 2  # Redondear al 0.5 superior
    vmax = max(vmax, 1)
    boundaries = np.arange(0, vmax + 0.5, 0.5)
    n_colors = len(boundaries) - 1
    colors = [plt.cm.jet(i / max(n_colors - 1, 1)) for i in range(n_colors)]
    discrete_cmap = mcolors.ListedColormap(colors)
    norm = mcolors.BoundaryNorm(boundaries, discrete_cmap.N)
    
    fig_height = max(8, min(14, 0.6 * n_months + 4))
    fig, ax = plt.subplots(figsize=(18, fig_height))
    im = ax.imshow(speed_matrix, aspect='auto', cmap=discrete_cmap, norm=norm, extent=[-0.5, 23.5, n_months - 0.5, -0.5])
    
    for idx in range(n_months):
        for hour in range(24):
            data = wind_data.get((idx, hour), {})
            dominant = data.get('dominant', [])
            if not dominant:
                continue
            x, y = hour, idx
            max_freq = max(d['frequency'] for d in dominant)
            min_freq = min(d['frequency'] for d in dominant) if len(dominant) > 1 else max_freq
            for dir_info in dominant:
                angle_rad = np.radians(dir_info['angle'] + 180)
                if len(dominant) > 1 and max_freq > min_freq:
                    norm_freq = (dir_info['frequency'] - min_freq) / (max_freq - min_freq)
                    arrow_length = ARROW_SCALE_MIN + (ARROW_SCALE_MAX - ARROW_SCALE_MIN) * (ARROW_SIZE_RATIO + (1 - ARROW_SIZE_RATIO) * norm_freq)
                else:
                    arrow_length = ARROW_SCALE_MAX
                dx = arrow_length * np.sin(angle_rad)
                dy = -arrow_length * np.cos(angle_rad)
                rel_size = dir_info['frequency'] / max_freq if max_freq > 0 else 1
                head_width = 0.12 + 0.08 * rel_size
                head_length = 0.08 + 0.04 * rel_size
                ax.add_patch(mpatches.FancyArrow(x, y, dx, dy, width=0.05+0.03*rel_size, head_width=head_width, head_length=head_length, length_includes_head=True, fc='white', ec='black', lw=0.5, zorder=3))
    
    ax.set_xticks(range(24))
    ax.set_xticklabels([f'{h:02d}' for h in range(24)], rotation=0, ha='center', fontsize=12)
    ax.set_xlabel('Hora', fontsize=12, fontweight='bold')
    
    months_names = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
    y_labels = []
    prev_year = None
    for year, month in month_list:
        if year != prev_year:
            y_labels.append(f"{months_names[month-1]} {year}")
            prev_year = year
        else:
            y_labels.append(months_names[month-1])
    ax.set_yticks(range(n_months))
    ax.set_yticklabels(y_labels, fontsize=12)
    ax.set_ylabel('Mes', fontsize=12, fontweight='bold')
    
    cbar = plt.colorbar(im, ax=ax, shrink=0.8, pad=0.02, ticks=boundaries)
    cbar.set_label('Velocidad promedio (m/s)', fontsize=11, fontweight='bold')
    ax.set_title(title or 'Intensidad y Dirección por Hora y Mes', fontsize=13, fontweight='bold', pad=20)
    ax.set_xticks(np.arange(-0.5, 24, 1), minor=True)
    ax.set_yticks(np.arange(-0.5, n_months, 1), minor=True)
    ax.grid(which='minor', color='white', linestyle='-', linewidth=0.3, alpha=0.5)
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path+'/5-Perfil_diario_mensual_vel_dir.png', dpi=150, bbox_inches='tight', facecolor='white')