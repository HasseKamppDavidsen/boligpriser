#%%

import streamlit as st
import json
import requests
import pandas as pd
import plotly.express as px

# import geopy.distance

# coords_1 = (52.2296756, 21.0122287)
# coords_2 = (52.406374, 16.9251681)

# print (geopy.distance.geodesic(coords_1, coords_2).m)

@st.cache
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

#######################################################################################

with st.sidebar:
    postNr = st.number_input("Postnummer", min_value=0, format="%i")
    soldYear = st.number_input("Tidligste salgsår", min_value=1990, format="%i")

#%%

if st.button('Hent data'):

    df = fnc_getSoldData(postNr, soldYear)
    
    #df.info()

    #%%
    fig = px.scatter(df, x='soldDate', y='price')#, color='GEOL_LEG_C', symbol='GEOL_LEG_C')

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

if st.button('Konverter data'):
    

    df = fnc_getSoldData(postNr, soldYear)
    #geopy.distance.geodesic(coords_1, coords_2).m
    st.dataframe(df)