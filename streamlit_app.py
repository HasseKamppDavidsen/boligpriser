#%%

# streamlit run streamlit_app.py --theme.base "dark"

import streamlit as st
import json
import requests
import pandas as pd
import plotly.express as px
import geopy.distance
from streamlit_folium import folium_static
import folium
import openpyxl

#st.set_page_config(layout="wide")

#%%

# Get all Postal codes 
# https://api.dataforsyningen.dk/postnumre
@st.cache
def fnc_getPostalCode():
    # response = requests.get("https://api.dataforsyningen.dk/postnumre")
    # tRes = json.loads(response.text)

    # dfh = pd.json_normalize(tRes)

    dfh = pd.read_excel("postalCodes.xlsx")
    
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
@st.cache(allow_output_mutation=True, show_spinner=False) # Mutations??
def fnc_getSoldData(postNr: list, soldYear: int):

    with st.spinner('Henter salgsdata fra Boliga...'):
        
        dfSold = pd.DataFrame()

        for cntPst in postNr:
            response = requests.get(f"https://api.boliga.dk/api/v2/sold/search/results?zipcodeFrom={cntPst}&zipcodeTo={cntPst}")
            tRes = json.loads(response.text)

            dfh = pd.json_normalize(tRes)
            pages = dfh.iloc[0,4]
            df = pd.DataFrame()
            for x in range(pages):
                apiUrl = f"https://api.boliga.dk/api/v2/sold/search/results?zipcodeFrom={cntPst}&zipcodeTo={cntPst}&page={x+1}"
                response = requests.get(apiUrl)
                sold = json.loads(response.text)
                dftmp = pd.json_normalize(sold, record_path=['results'])
                dftmp['soldDate'] =  pd.to_datetime(dftmp['soldDate'], infer_datetime_format=True)

                dateYear = dftmp.iloc[0,4].year

                if dateYear == soldYear-1:
                    break

                df = pd.concat([df, dftmp])

            dfSold = pd.concat([dfSold, df]) 
    
    #st.success('Done!')

    return dfSold  

#@st.cache
def fnc_findAdressInRadius(dfAdress, dfSold, propType):
    
    dfSold['Distance_m'] = "" 

    if len(dfAdress)>0:
        coords_adr = (dfAdress['adgangsadresse.y'], dfAdress['adgangsadresse.x'])
    else:
        coords_adr = (55.79044716, 12.48303272)

    dfSold = dfSold.reset_index(drop=True)
    for index, row in dfSold.iterrows():
        coords_sold = (row['latitude'], row['longitude'])
        distm = geopy.distance.geodesic(coords_adr, coords_sold).m
        #print(index, coords_adr, coords_sold, distm)
        dfSold.loc[index, 'Distance_m'] = distm
        
    return dfSold

# Generate city name in multiselect
def fnc_getName(pstNr, dfpst):
    byNavn = dfpst.query("nr == @pstNr").iloc[0,3] 
    return str(pstNr) + " - " + str(byNavn)

def fnc_getPropertyName(propID, dfProp):
    propStr = dfProp.query("ID == @propID").iloc[0,1] 
    return str(propStr)

dfPropType = pd.DataFrame({'ID':[1,2,3,4,5], 'Type':['Villa', 'Rækkehus', 'Ejerlejlighed', 'Fritidshus', 'Landejendom']})

#%%

#######################################################################################
# Desclare empty variables
if 'ssHentData' not in st.session_state:
    st.session_state['ssHentData'] = False

# if st.session_state['ssHentData'] == False:
#     dfSold = pd.DataFrame()

dfSoldDistFilt = pd.DataFrame()
dfSoldDist = pd.DataFrame()

dfSoldDist['Distance_m'] = 0
featGrp_Solgte = folium.FeatureGroup("Solgte ejendomme")
featGrp_Adress = folium.FeatureGroup("Valgte adresse")
featGrp_PostNr = folium.FeatureGroup("Postnumre")

postNr = []

if 'ssHentData' not in st.session_state:
    st.session_state['ssHentData'] = False

#######################################################################################
# Sidebare
with st.sidebar:
    
    dfpst = fnc_getPostalCode()
    
    with st.form("formHentData"):
        postNr = st.multiselect("Vælg postnummer", dfpst["nr"], format_func=lambda pstNr: fnc_getName(pstNr, dfpst))
        soldYear = st.number_input("Tidligste salgsår", value=2021, min_value=1990, format="%i")
        adresseStr = st.text_input("Skriv adresse der ligger i det først valgte postnummer", value="Hjertebjergvej 12")
        distFilt_m = st.number_input("Søge afstand fra adresse", value=500, step=250, min_value=100, max_value=10000, format="%i")
        propType = st.multiselect("Vælg boligtype", dfPropType["ID"], format_func=lambda propNr: fnc_getPropertyName(propNr, dfPropType))
        blShowPostCd = st.checkbox("Vis postnummer på kortet")

        submitHentData = st.form_submit_button("Opdater visning")

        if submitHentData:
            if len(postNr)>0:
                dfSold = fnc_getSoldData(postNr, soldYear)
                dfadr = fnc_getAdressCoordinates(adresseStr, postNr[0])
                if len(dfadr.index)>0:
                    dfSoldDist = fnc_findAdressInRadius(dfadr, dfSold, propType)
                    dfSoldDistFilt = dfSoldDist.query("Distance_m < @distFilt_m")
                    st.session_state['ssHentData'] = True
                else:                
                    st.warning('Adressen blev ikke fundet inden for det først valgte postnummer', icon="⚠️")
                
            else:
                st.warning('Vælg først postnummer', icon="⚠️")

#######################################################################################
# Main page


# st.dataframe(dfSold)
# st.dataframe(dfadr)
# st.dataframe(dfSoldDist)
# st.dataframe(dfSoldDist)

if len(dfSoldDist.index)>0:
    coords_adr = (dfadr['adgangsadresse.y'], dfadr['adgangsadresse.x'])
    map = folium.Map(location=coords_adr, zoom_start=15, tiles='Cartodb dark_matter')#,'CartoDB positron'])
    
    # Read topo with postal codes
    with open('postnumre.json') as f:
        postNr_topo = json.load(f)

    # Add topo to map
    cp = folium.Choropleth(geo_data=postNr_topo,
             topojson='objects.postnumre',
             key_on='feature.properties.Postnummer',
             fill_color='white', 
             fill_opacity=0.2,
             line_color='black', 
             line_opacity=0.5).add_to(featGrp_PostNr)
    
    featGrp_PostNr.add_to(map)

    if blShowPostCd:
        folium.GeoJsonTooltip(['Postnummer']).add_to(cp.geojson)

    # Add adress
    folium.CircleMarker([dfadr['adgangsadresse.y'], dfadr['adgangsadresse.x']],
            radius=10,
            popup="Adresse:" + str(dfadr['adgangsadresse.vejnavn']) + " " + str(dfadr['adgangsadresse.husnr']),
            color='#D6D3D2',
            fill=True,
            fill_color='#3C4C39',
            fill_opacity=0.7,
            parse_html=False).add_to(featGrp_Adress) 

    featGrp_Adress.add_to(map)

    if len(dfSoldDistFilt.index) > 0:
        for index, row in dfSoldDistFilt.iterrows():
            folium.CircleMarker([row['latitude'], row['longitude']],
            radius=6,
            popup="Adresse: " + str(row['address']) + " Type: " + str(row['propertyType']),
            color='#000000',
            fill=True,
            fill_color='#ffffff',
            fill_opacity=0.7,
            parse_html=False).add_to(featGrp_Solgte) 

        featGrp_Solgte.add_to(map)

        folium.LayerControl().add_to(map)

        with st.expander("Oversigtskort", expanded=True):
            folium_static(map, width=670, height=500)
        
        with st.expander("Plot over priser"):
            fig = px.scatter(dfSoldDistFilt, x='soldDate', y='price')#, color='GEOL_LEG_C', symbol='GEOL_LEG_C')
            st.plotly_chart(fig)
    
        with st.expander("Rådata"):
            st.dataframe(dfSoldDistFilt)
    

# else:
#     if st.session_state['ssHentData'] == False:
#         st.header("Hent først data for én eller flere postnumre")
#     elif st.session_state['ssHentData'] == True:
#         st.header("Angiv adresse og opdater visning")





###############################################################################
# Trash and test

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

    
#if st.button('Konverter data'):
        #st.dataframe(df)


#%%


# dfpst = fnc_getPostalCode()
# dfpst.to_excel("postalCodes.xlsx")  

#dfpst = pd.read_excel("postalCodes.xlsx")

#%%

# dfpst = fnc_getPostalCode()
# pstNr = '2800'
# dfbyNavn = dfpst.query("nr == @pstNr").iloc[0,2] 
# byNavn = dfbyNavn.iloc[0,2] 

#states_topo.keys()
#states_topo['objects'].keys()
#postNr_topo['objects']['postnumre'].keys()
#postNr_topo['objects']['postnumre']['geometries'][0]['properties']['POSTNR_TXT']

# with open('postnumre.json') as f:
#     postNr_topo = json.load(f)

# folium_map = folium.Map(location=[55.79044716, 12.48303272],
#                         zoom_start=10,
#                         tiles="OpenStreetMap")

# cp = folium.Choropleth(geo_data=postNr_topo,
#              topojson='objects.postnumre',
#              key_on='feature.properties.POSTNR_TXT',
#              fill_color='white', 
#              fill_opacity=0.2,
#              line_color='black', 
#              line_opacity=0.5).add_to(folium_map)

# folium.GeoJsonTooltip(['POSTNR_TXT']).add_to(cp.geojson)
# folium.LayerControl().add_to(folium_map)

# folium_map

#dfPropType = pd.DataFrame({'ID':[1,2,3,4,5], 'Type':['Villa', 'Rækkehus', 'Ejerlejlighed', 'Fritidshus', 'Landejendom']})