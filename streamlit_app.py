#%%

import streamlit as st
import json
import requests
import pandas as pd
import plotly.express as px
import geopy.distance
from streamlit_folium import folium_static
import folium

# Get all Postal codes 
# https://api.dataforsyningen.dk/postnumre
@st.cache
def fnc_getPostalCode():
    response = requests.get("https://api.dataforsyningen.dk/postnumre")
    tRes = json.loads(response.text)

    dfh = pd.json_normalize(tRes)
    
    return dfh

# Look up adress
@st.cache
def fnc_getAdressCoordinates(adressStr: str, postNr: int):
    response = requests.get(f"https://api.dataforsyningen.dk/adgangsadresser/autocomplete?q={adressStr}&postnr={postNr}")
    tRes = json.loads(response.text)

    dfh = pd.json_normalize(tRes)
    if len(dfh.index)>0:
        dfh = dfh.iloc[0,:]

    return dfh
    # if adress does not exists returns nothing, check for error

# Get sold properties
@st.cache(allow_output_mutation=True) # Mutations??
def fnc_getSoldData(postNr: int, soldYear: int):
    response = requests.get(f"https://api.boliga.dk/api/v2/sold/search/results?zipcodeFrom={postNr}&zipcodeTo={postNr}")

    tRes = json.loads(response.text)

    dfh = pd.json_normalize(tRes)
    pages = dfh.iloc[0,4]
    df = pd.DataFrame()
    
    for x in range(pages):
        apiUrl = f"https://api.boliga.dk/api/v2/sold/search/results?zipcodeFrom={postNr}&zipcodeTo={postNr}&page={x+1}"
        response = requests.get(apiUrl)
        sold = json.loads(response.text)
        dftmp = pd.json_normalize(sold, record_path=['results'])
        dftmp['soldDate'] =  pd.to_datetime(dftmp['soldDate'], infer_datetime_format=True)

        dateYear = dftmp.iloc[0,4].year

        if dateYear == soldYear-1:
            break

        df = pd.concat([df, dftmp])

    return df  

#@st.cache
def fnc_findAdressInRadius(dfAdress, dfSold):
    
    dfSold['Distance_m'] = "" 

    if len(dfAdress)>0:
        coords_adr = (55.79044716, 12.48303272)#(dfAdress['adgangsadresse.y'], dfAdress['adgangsadresse.x'])
    else:
        coords_adr = (55.79044716, 12.48303272)

    dfSold = dfSold.reset_index(drop=True)
    for index, row in dfSold.iterrows():
        coords_sold = (row['latitude'], row['longitude'])
        distm = geopy.distance.geodesic(coords_adr, coords_sold).m
        #print(index, coords_adr, coords_sold, distm)
        dfSold.loc[index, 'Distance_m'] = distm
        
    return dfSold

#%%

#######################################################################################
dfSoldDistFilt = pd.DataFrame()
dfSoldDist = pd.DataFrame()
dfSoldDist['Distance_m'] = 0
featGrp_Solgte = folium.FeatureGroup("Solgte ejendomme")
featGrp_Adress = folium.FeatureGroup("Valgte adresse")

with st.sidebar:
    postNr = st.number_input("Postnummer", value=2830, min_value=0, format="%i")
    soldYear = st.number_input("Tidligste salgsår", value=2020, min_value=2015, format="%i")
    distFilt_m = st.number_input("Søge afstand fra adresse", value=500, min_value=100, max_value=10000, format="%i")

    if st.button('Hent data'):
        #dfpst = fnc_getPostalCode()
        dfadr = fnc_getAdressCoordinates("Hjertebjergvej 12", postNr)
        dfSold = fnc_getSoldData(postNr, soldYear)
        dfSoldDist = fnc_findAdressInRadius(dfadr, dfSold)
        dfSoldDistFilt = dfSoldDist.query("Distance_m < @distFilt_m")

        st.write(len(dfSoldDistFilt.index))


if len(dfSoldDistFilt.index)>0:
    #st.dataframe(dfSoldDistFilt)
    #Plot with center of jordstykke as center of map
    coords_adr = (dfadr['adgangsadresse.y'], dfadr['adgangsadresse.x'])
    map = folium.Map(location=coords_adr, zoom_start=15, tiles='CartoDB positron')
    
    # Add adress
    folium.CircleMarker([dfadr['adgangsadresse.y'], dfadr['adgangsadresse.x']],
            radius=10,
            popup="Adresse:" + "Hjertebjergvej 12",
            color='green',
            fill=True,
            fill_color='#cc0000',
            fill_opacity=0.7,
            parse_html=False).add_to(featGrp_Solgte) 

    featGrp_Adress.add_to(map)

    if len(dfSoldDistFilt.index) > 0:
        for index, row in dfSoldDistFilt.iterrows():
            folium.CircleMarker([row['latitude'], row['longitude']],
            radius=6,
            popup="Adresse: " + str(row['address']) + " Type: " + str(row['propertyType']),
            color='blue',
            fill=True,
            fill_color='#3186cc',
            fill_opacity=0.7,
            parse_html=False).add_to(featGrp_Solgte) 

        featGrp_Solgte.add_to(map)

        folium.LayerControl().add_to(map)
    
    folium_static(map)#, width=1250, height=500)
    
# else:
#     map = folium.Map(location=[55, 12], zoom_start=17, tiles='CartoDB positron')

# st.title('EDD Dataudtræk')

# folium_static(map, width=1250, height=500)

    #%%
    fig = px.scatter(dfSoldDistFilt, x='soldDate', y='price')#, color='GEOL_LEG_C', symbol='GEOL_LEG_C')

    # fig.update_layout(
    #     title={
    #         'text': 'Depth vs IVAN_IVAR',
    #         'y':1.0,
    #         'x':0.0,
    #         #'xanchor': 'center',
    #         #'yanchor': 'top'
    #         },
    #     yaxis_title="Depth (m b.g.)",
    #     xaxis_title="Undistributed Vane shear strength (kPa)",
    #     #xaxis={'side':'top'},
    #     width = 600,
    #     height = 600,
    #     #paper_bgcolor='rgba(0,0,0,0)',
    #     #plot_bgcolor='rgba(0,0,0,0)'
    # )

    # fig.update_xaxes(showline=True, linewidth=1, linecolor='black', mirror=True, gridcolor='Black')
    # fig.update_yaxes(showline=True, linewidth=1, linecolor='black', mirror=True, gridcolor='Black')

    st.plotly_chart(fig)

#if st.button('Konverter data'):
        #st.dataframe(df)


