#!/usr/bin/env python
# coding: utf-8

# In[ ]:

def utm2lonlat(Easting, Northing,utm_zone = 18, northern_hemisphere = False):
    from pyproj import CRS, Transformer, Proj

    #Coordinates in UTM Easting and Northing
    if northern_hemisphere:
        utm_crs = CRS(f"EPSG:326{utm_zone}")
    else:
        utm_crs = CRS(f"EPSG:327{utm_zone}")   
    wgs84_crs = CRS("EPSG:4326")
    transformer = Transformer.from_crs(utm_crs, wgs84_crs, always_xy=True)
    lon, lat = transformer.transform(Easting, Northing)    
    return lon, lat


def lonlat2utm(lon, lat):
    """Convert WGS84 latitude/longitude to UTM coordinates."""
    from pyproj import CRS, Transformer

    utm_zone = int((float(lon) + 180) / 6) + 1
    northern_hemisphere = float(lat) >= 0
    if northern_hemisphere:
        utm_crs = CRS(f"EPSG:326{utm_zone}")
    else:
        utm_crs = CRS(f"EPSG:327{utm_zone}")
    wgs84_crs = CRS("EPSG:4326")
    transformer = Transformer.from_crs(wgs84_crs, utm_crs, always_xy=True)
    easting, northing = transformer.transform(float(lon), float(lat))
    return easting, northing, utm_zone, northern_hemisphere
    

# In[ ]:
def magnetic_correction(t,Easting, Northing, utm_zone = 18, northern_hemisphere = False):
    """
    For a specific datetime object
    """
    from pygeomag import GeoMag
    import pandas as pd
    import numpy as np
    from datetime import datetime

    lon, lat = utm2lonlat(
        Easting, Northing, utm_zone=utm_zone, northern_hemisphere=northern_hemisphere
    )

    # includes leap years
    if t.year % 4 == 0:
        days_in_year = 366
    else:
        days_in_year = 365

    # time in years
    time = (
        t.year
        + (t.month - 1) / 12
        + (t.day - 1) / days_in_year
        + t.hour / (days_in_year * 24)
        + t.minute / (days_in_year * 24 * 60)
    )

    if time < 2025:
        geo_mag = GeoMag(coefficients_file="wmm/WMM_2020.COF")
        model = "WMM-2020"
    else:
        geo_mag = GeoMag(coefficients_file="wmm/WMM_2025.COF")
        model = "WMM-2025"

    result = geo_mag.calculate(glat=lat, glon=lon, alt=0, time=time)
    uncertainty = result.calculate_uncertainty()
    declination = result.d
    error = uncertainty.d

    fig = magnetic_correction_image(
        t, declination, error, model, Easting, Northing, utm_zone, northern_hemisphere
    )

    return lon, lat, declination, error, fig


def _apply_declination_to_directions(df, declination):
    """Add declination to WD and wrap into [0, 360).

    Uses array math so DatetimeIndex frames are handled correctly (integer
    label indexing on a datetime Series raises KeyError).
    """
    import numpy as np

    wd = np.asarray(df["WD"], dtype=float) + np.asarray(declination, dtype=float)
    wd = np.round(wd, 2)
    wd = np.mod(wd, 360.0)
    df["WD"] = wd


def magnetic_correction_wind(df,Easting, Northing, utm_zone=18,northern_hemisphere = False):
    """
    For the midpoint of wind measurement. Takes a dataframe with a datetime index. 
    """
    from pygeomag import GeoMag
    import numpy as np

    lon, lat = utm2lonlat(Easting, Northing, utm_zone = utm_zone, northern_hemisphere = northern_hemisphere)  
    
    i = int(len(df)/2)
    t = df.index[i]
        #includes leap years
    if t.year % 4 == 0:
        days_in_year =366
    else:
        days_in_year =365
            
    #time in years
    time = t.year+(t.month-1)/12+(t.day-1)/days_in_year+t.hour/(days_in_year*24)+t.minute/(days_in_year*24*60)

    if time < 2025:
        geo_mag = GeoMag(coefficients_file="wmm/WMM_2020.COF")
        model = "WMM-2020"
    elif time >= 2025:
        geo_mag = GeoMag(coefficients_file="wmm/WMM_2025.COF")
        model = "WMM-2025"
            
    result = geo_mag.calculate(glat=lat, glon=lon, alt=0, time=time)
    uncertainty = result.calculate_uncertainty()
    declination = result.d
    error = uncertainty.d

    _apply_declination_to_directions(df, declination)
    fig = magnetic_correction_image(t, declination, error, model, Easting, Northing, utm_zone, northern_hemisphere)

    return declination, error, lon, lat, fig


def magnetic_correction_complete(df,Easting, Northing, utm_zone = 18, northern_hemisphere = False):
    """
    For every timestamp of the measurement. Takes a dataframe with a datetime index. Returns an array of decilations and a mean error
    """
    from pygeomag import GeoMag
    import numpy as np

    lon, lat = utm2lonlat(Easting, Northing,utm_zone = utm_zone, northern_hemisphere = northern_hemisphere)    
    declination = []
    error = []
    for i in range(len(df)):
        t = df.index[i]
        #includes leap years
        if t.year % 4 == 0:
            days_in_year =366
        else:
            days_in_year =365
            
        #time in years
        time = t.year+(t.month-1)/12+(t.day-1)/days_in_year+t.hour/(days_in_year*24)+t.minute/(days_in_year*24*60)

        if time < 2025:
            geo_mag = GeoMag(coefficients_file="wmm/WMM_2020.COF")
            model = "WMM-2020"
        elif time >= 2025:
            geo_mag = GeoMag(coefficients_file="wmm/WMM_2025.COF")
            model = "WMM-2025"
            
        result = geo_mag.calculate(glat=lat, glon=lon, alt=0, time=time)
        uncertainty = result.calculate_uncertainty()
        declination.append(result.d)
        error.append(uncertainty.d)
        
    mean_error = np.mean(error)
    
    _apply_declination_to_directions(df, declination)
    fig = magnetic_correction_image(t, declination[-1], error[-1], model, Easting, Northing, utm_zone, northern_hemisphere)

    return declination, mean_error, lon, lat, fig 

def magnetic_correction_image(t, declination, error, model, Easting, Northing, utm_zone = 18, northern_hemisphere = False, H = 5000, W = 200, kilometers_covered = 18):
    """
    Generates magnetic correction image
    """
    import numpy as np
    import matplotlib.pyplot as plt
    import matplotlib as mpl
    import pyproj
    from pyproj import CRS, Transformer, Proj
    import math
    import cartopy.crs as ccrs
    import cartopy.io.img_tiles as cimgt
    import matplotlib.patches as mpatches
    import matplotlib.lines as mlines
    from datetime import datetime

    #Coordinates in UTM Easting and Northing
    if northern_hemisphere == True:
        utm_crs = CRS(f"EPSG:326{utm_zone}")
        hemisphere = 'north'
        southern_hemisphere = False
    else:
        utm_crs = CRS(f"EPSG:327{utm_zone}")
        hemisphere = 'south'
        southern_hemisphere = True

    wgs84_crs = CRS("EPSG:4326")
    transformer = Transformer.from_crs(utm_crs, wgs84_crs, always_xy=True)

    lon, lat = transformer.transform(Easting, Northing)

    #Coordinates for quadrant lines adjusted for utm projection deformation with respect to lon and lat
    p = Proj(f"+proj=utm +zone={utm_zone} +{hemisphere} +datum=WGS84 +units=m") # +no_defs")

    #Easting, Northing = p(lon, lat)
    lon, lat = p(Easting, Northing,inverse = True)
    lonN, latN = p(Easting, Northing+H,inverse = True)
    EastingN, NorthingN = p(lon, latN)
    lonS, latS = p(Easting, Northing-H,inverse = True)
    EastingS, NorthingS = p(lon, latS)
    lonE, latE = p(Easting+H, Northing,inverse = True)
    EastingE, NorthingE = p(lonE, lat)
    lonW, latW = p(Easting-H, Northing,inverse = True)
    EastingW, NorthingW = p(lonW, lat)    

    #Draw map centered at lon lat coords, convert to UTM projection to avoid distortion of compass shapes
    p = Proj(proj='utm',zone=utm_zone,ellps='WGS84')
    Easting, Northing = p(lon, lat)
    extent = kilometers_covered*1000/2
    minE, maxE, minN, maxN = (Easting-extent*0.8, Easting+extent*0.8, Northing-extent, Northing+extent)
    URL='https://server.arcgisonline.com/ArcGIS/rest/services/World_Shaded_Relief/MapServer/tile/{z}/{y}/{x}.jpg'  
    request = cimgt.GoogleTiles(desired_tile_form='RGB', style='terrain', url=URL)
    proj = ccrs.UTM(utm_zone) #for the map and shapes
    proj2 = ccrs.UTM(utm_zone, southern_hemisphere) #for the lines
    
    fig = plt.figure(figsize=(2.6,3.5), facecolor="whitesmoke",layout='constrained')
    ax = plt.axes(projection=request.crs)
    ax.set_extent([minE, maxE, minN, maxN], crs=proj)
    ax.add_image(request, 13)

    #Text box with magnetic correction details
    props = dict(boxstyle = 'square', facecolor='lemonchiffon',ec='white', alpha=0.8)
    textstr='\n'.join((
        r'Modelo: WMM-2025',
        r'Longitud: %2.4f'%lon,
        r'Latitud: %2.4f'%lat,
        f'Fecha: {datetime.strftime(t,"%Y-%m-%d")}',
        r'Declinación: %2.2f'%declination,
        r'Incertidumbre: ±%0.2f'%error))
    ax.text(0.03,0.98,textstr, transform=ax.transAxes,fontsize= 'xx-small', va = 'top', bbox=props)
    
    #Draw compass with magnetic North needle composed of a wedge circle, quadrant lines and 4 rotating triangles
    x_sign = [[-1,-1],[-1,-1],[1,-1],[1,-1]]
    y_sign = [[1,-1],[1,-1],[1,1],[1,1]]
    Xrotation = [W * math.cos(declination * (math.pi / 180)), H * math.sin(declination * (math.pi / 180))]
    Yrotation = [W * math.sin(declination * (math.pi / 180)), H * math.cos(declination * (math.pi / 180))]
    DX = np.multiply(x_sign,Xrotation)
    DY = np.multiply(y_sign,Yrotation)

    x1 = [Easting-DX[0,0],Easting,Easting-DX[0,1]]
    y1 = [Northing-DY[0,0],Northing,Northing-DY[0,1]]
    x2 = [Easting+DX[1,0],Easting, Easting+DX[1,1]]
    y2 = [Northing+DY[1,0],Northing, Northing+DY[1,1]]
    x3 = [Easting+DX[2,0],Easting,Easting+DX[2,1]]
    y3 = [Northing+DY[2,0],Northing,Northing+DY[2,1]]
    x4 = [Easting-DX[3,0],Easting, Easting-DX[3,1]]
    y4 = [Northing-DY[3,0],Northing, Northing-DY[3,1]]

    ax.add_line(mlines.Line2D([EastingE,EastingW], [NorthingE,NorthingW], lw=1, color = 'k',alpha = 0.5, transform=proj2,zorder=1))
    ax.add_line(mlines.Line2D([EastingN,EastingS], np.column_stack([NorthingN,NorthingS]),lw=1, color = 'k', alpha = 0.5,transform=proj2,zorder=1))
    ax.add_patch(mpatches.Wedge([Easting, Northing], H, 0, 360, width=100,alpha=0.6, color = 'gainsboro', ec='k',transform=proj))
    ax.text(Easting-300, Northing+H+200,fontsize=14, s = 'N',color='k', transform=proj)
    ax.add_patch(mpatches.Polygon(np.column_stack([x2, y2]), color='gainsboro', ec='lightgray',transform=proj))
    ax.add_patch(mpatches.Polygon(np.column_stack([x3, y4]), color='silver', ec='darkgray', transform=proj))
    ax.add_patch(mpatches.Polygon(np.column_stack([x4, y3]), color='lightsalmon', ec='salmon',transform=proj))
    ax.add_patch(mpatches.Polygon(np.column_stack([x1, y1]), color='r', ec='crimson',transform=proj))
    ax.add_patch(mpatches.Circle((Easting, Northing), 100, color = 'darkgray', ec='dimgray', transform=proj))

    return fig