#%%

# streamlit run streamlit_app.py --theme.base "dark"

from smtplib import SMTPServerDisconnected
import streamlit as st
import json
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import geopy.distance
from streamlit_folium import folium_static
import folium
import openpyxl
import matplotlib as mpl
import datetime 


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
def fnc_getSoldData(postNr: list, soldYear: int, dfPropType):

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

            for index, row in dfPropType.iterrows():
                dfSold.loc[dfSold['propertyType'] == row['ID'], "propertyName" ] = row['Type']
    
    return dfSold  

#@st.cache
def fnc_findAdressInRadius(dfAdress, dfSold, propType, priceInterval):
    
    dfSold['Distance_m'] = "" 
    dfPropFilter = pd.DataFrame()

    if len(dfAdress)>0:
        coords_adr = (dfAdress['adgangsadresse.y'], dfAdress['adgangsadresse.x'])
    else:
        coords_adr = (55.79044716, 12.48303272)

    dfSold = dfSold.reset_index(drop=True)
    for index, row in dfSold.iterrows():
        coords_sold = (row['latitude'], row['longitude'])
        distm = geopy.distance.geodesic(coords_adr, coords_sold).m
        dfSold.loc[index, 'Distance_m'] = distm

    if len(propType)>0:    
        for propID in propType:
            dfPropFilter_tmp = dfSold.query("propertyType == @propID")
            dfPropFilter = pd.concat([dfPropFilter, dfPropFilter_tmp])
        dfSold = dfPropFilter

    priceType = priceInterval[2]
    minPrice = priceInterval[0]
    dfSold = dfSold.query("{} >= @minPrice".format(priceType))
    maxPrice = priceInterval[1]
    dfSold = dfSold.query("{} <= @maxPrice".format(priceType))

    dfSold['roll_sqmPrice'] = dfSold.sqmPrice.rolling(30, min_periods=5).mean()
    dfSold['roll_Price'] = dfSold.price.rolling(30, min_periods=5).mean()

    dfSold.sort_values(by=['soldDate'], inplace=True)

    return dfSold

def fnc_findColorValue(dfSoldDistFilt):
    sqmPriceMax = dfSoldDistFilt['sqmPrice'].max()
    sqmPriceMin = dfSoldDistFilt['sqmPrice'].min()
    dfSoldDistFilt['ColorScale'] = (dfSoldDistFilt['sqmPrice']-sqmPriceMin)/(sqmPriceMax-sqmPriceMin)

    return dfSoldDistFilt

# Generate city name in multiselect
def fnc_getName(pstNr, dfpst):
    byNavn = dfpst.query("nr == @pstNr").iloc[0,3] 
    return str(pstNr) + " - " + str(byNavn)

def fnc_getPropertyName(propID, dfProp):
    propStr = dfProp.query("ID == @propID").iloc[0,1] 
    return str(propStr)

def fnc_findColor(priceval):
    myColor = [(2*priceval),(2*(1 - priceval)),0]
    newColor = []

    for c in myColor:
        if c > 1:
            newColor.append(1)
        else:
            newColor.append(c)

    return mpl.colors.to_hex(newColor)

def popHtml(row):

    strAddress = row['address']
    strSoldDate = row['soldDate'].strftime("%Y-%m-%d")
    strPrice = '{:,}'.format(row['price'])
    strSize = row['size']
    strType = row['propertyName']

    html =f"""
        <html>
            <tbody>
                <table style="width: 250px;">
                    <tr>
                        <th style="background-color:#eeeeee;border: 1px solid black;padding-left: 5px;padding-right: 5px;"><b>Parameter</b></th>
                        <th style="background-color:#eeeeee;border: 1px solid black;padding-left: 5px;padding-right: 5px;"><b>Værdi</b></th>
                    </tr>
                    <tr>
                        <td style="border: 1px solid black;padding-left: 5px;padding-right: 5px;">Adresse</td>
                        <td style="border: 1px solid black;padding-left: 5px;padding-right: 5px;">{strAddress}</td>
                    </tr>    
                    <tr>
                        <td style="border: 1px solid black;padding-left: 5px;padding-right: 5px;">Salgsdato</td>
                        <td style="border: 1px solid black;padding-left: 5px;padding-right: 5px;">{strSoldDate}</td>
                    </tr> 
                    <tr>
                        <td style="border: 1px solid black;padding-left: 5px;padding-right: 5px;">Pris (DKK)</td>
                        <td style="border: 1px solid black;padding-left: 5px;padding-right: 5px;">{strPrice}</td>
                    </tr>   
                    <tr>
                        <td style="border: 1px solid black;padding-left: 5px;padding-right: 5px;">Boligareal (m2)</td>
                        <td style="border: 1px solid black;padding-left: 5px;padding-right: 5px;">{strSize}</td>
                    </tr>   
                    <tr>
                        <td style="border: 1px solid black;padding-left: 5px;padding-right: 5px;">Boligtype</td>
                        <td style="border: 1px solid black;padding-left: 5px;padding-right: 5px;">{strType}</td>
                    </tr>     

                </table>       
            </tbody>
        </html>
    """
    return html

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
    
    st.title("Solgte boliger i DK")

    dfpst = fnc_getPostalCode()
    
    with st.form("formHentData"):
        postNr = st.multiselect("Vælg postnummer", dfpst["nr"], format_func=lambda pstNr: fnc_getName(pstNr, dfpst))
        soldYear = st.number_input("Tidligste salgsår", value=2021, min_value=1990, format="%i")
        adresseStr = st.text_input("Skriv adresse der ligger i det først valgte postnummer", value="Hjertebjergvej 12")
        distFilt_m = st.number_input("Søge afstand fra adresse", value=500, step=250, min_value=100, max_value=10000, format="%i")
        propType = st.multiselect("Vælg boligtype", dfPropType["ID"],help="Hej", format_func=lambda propNr: fnc_getPropertyName(propNr, dfPropType))
        blShowPostCd = st.checkbox("Vis postnummer på kortet")

        submitHentData = st.form_submit_button("Opdater visning")

        with st.expander("Indstillinger"):
            
            yaxisParameter = st.selectbox("Vælg parameter til plot", ['Kvadratmeterpriser','Salgspriser'])
            
            if yaxisParameter == 'Kvadratmeterpriser':
                minInterval = 0
                maxInterval = 200000
                priceType = 'sqmPrice'
            else:
                minInterval = 0
                maxInterval = 100000000
                priceType = 'price'

            priceInterval = st.slider(
                'Vælg interval for priser',
                min_value=minInterval, 
                max_value=maxInterval, 
                value=(minInterval, maxInterval),
                step=5000)
            
            priceInterval = list(priceInterval)
            priceInterval.append(priceType)

        if submitHentData:
            if len(postNr)>0:
                dfSold = fnc_getSoldData(postNr, soldYear, dfPropType)
                dfadr = fnc_getAdressCoordinates(adresseStr, postNr[0])
                if len(dfadr.index)>0:
                    dfSoldDist = fnc_findAdressInRadius(dfadr, dfSold, propType, priceInterval)
                    if len(dfSoldDist.index)>0:
                        dfSoldDistFilt = dfSoldDist.query("Distance_m < @distFilt_m")
                        dfSoldDistFilt = fnc_findColorValue(dfSoldDistFilt)
                        if len(dfSoldDistFilt.index)>0:
                            st.session_state['ssHentData'] = True
                        else:
                            st.warning('Ingen solgte boliger blev fundet', icon="⚠️")
                    else:
                        st.warning('Ingen solgte boliger blev fundet', icon="⚠️")
                else:                
                    st.warning('Adressen blev ikke fundet inden for det først valgte postnummer', icon="⚠️")
                
            else:
                st.warning('Vælg først postnummer', icon="⚠️")

#######################################################################################
# Main page

if len(dfSoldDist.index)>0:
    coords_adr = (dfadr['adgangsadresse.y'], dfadr['adgangsadresse.x'])
    map = folium.Map(location=coords_adr, zoom_start=15, tiles='Stamen Toner')#,'CartoDB positron']) / Cartodb dark_matter
    
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
            fol_c = folium.CircleMarker([row['latitude'], row['longitude']],
                                        radius=6,
                                        color='#000000',
                                        fill=True,
                                        fill_color=fnc_findColor(row['ColorScale']),
                                        fill_opacity=0.7,
                                        parse_html=False)
            
            html = popHtml(row)
            folium.Popup(folium.Html(html, script=True)).add_to(fol_c)
                
            fol_c.add_to(featGrp_Solgte) 

        
        featGrp_Solgte.add_to(map)

        folium.LayerControl().add_to(map)

        with st.expander("Oversigtskort", expanded=True):
            folium_static(map, width=670, height=500)
        
        with st.expander("Plot over priser", expanded=False):

            #yaxisParameter = st.selectbox("Vælg parameter til graf", ['Kvadratmeterpriser','Salgspriser'])

            #yaxisParameter = 'Kvadratmeterpriser'

            if yaxisParameter == 'Salgspriser':
                yValue = 'price'
                yValueRoll = 'roll_Price'
                yAxisTitle = 'Salgspris (DKK)'
            else:
                yValue = 'sqmPrice'
                yValueRoll = 'roll_sqmPrice'
                yAxisTitle = 'Kvadratmeterpris (DKK/m2)'

            fig = px.scatter(
                dfSoldDistFilt, 
                x='soldDate', 
                y=yValue, 
                color="propertyName", 
                labels={"propertyName": "Boligtype"}
                )

            fig.update_layout(
                # title={
                #     'text': 'Indsæt titel her',
                #     'y':1.0,
                #     'x':0.0,
                #     #'xanchor': 'center',
                #     #'yanchor': 'top'
                #     },
                yaxis_title=yAxisTitle,
                xaxis_title="",
                #xaxis={'side':'top'},
                width = 670,
                height = 500,
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)'
            )

            fig.add_trace(
                go.Scatter(
                x=dfSoldDistFilt["soldDate"], 
                y=dfSoldDistFilt[yValueRoll],
                line=go.scatter.Line(color="gray"),
                showlegend=False)
                )

            fig.update_xaxes(
                showline=True, 
                linewidth=1, 
                mirror=True, 
                gridcolor='Black', 
                linecolor='black'
                )
            fig.update_yaxes(
                showline=True, 
                linewidth=1, 
                mirror=True, 
                gridcolor='Black',
                linecolor='black'
                )

            st.plotly_chart(fig)
    
        with st.expander("Rådata"):
            st.dataframe(dfSoldDistFilt)
    

else:
    if st.session_state['ssHentData'] == False:
        st.header("Hent først data for én eller flere postnumre")
    elif st.session_state['ssHentData'] == True:
        st.header("Angiv adresse og opdater visning")
    
    with st.expander("Oversigtskort", expanded=False):
        st.write("Intet at vise")
        
    with st.expander("Plot over priser"):
        st.write("Intet at vise")

    with st.expander("Rådata"):
        st.write("Intet at vise")


###############################################################################
# Trash and test