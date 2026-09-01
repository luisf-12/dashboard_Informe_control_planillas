import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Control de Planillas", layout="wide")
st.title("🚛 Emprestur - Control de Planillas")

archivo_subido = st.file_uploader("Sube el archivo exportado de Cronos (Excel)", type=["xlsx"])

if archivo_subido:
    df = pd.read_excel(archivo_subido)
    
    # 1. Limpieza usando los nombres EXACTOS de Cronos
    df['Numero Orden'] = df['Numero Orden'].astype(str).str.strip().str[:14]
    df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce')
    
    # 2. Calcular Fecha Máxima por Orden
    df['FECHA_MAX'] = df.groupby('Numero Orden')['Fecha'].transform('max')
    
    # 3. Validar si todas las planillas de la orden dicen "SI"
    df['PLANILLAS_OK'] = df.groupby('Numero Orden')['Planilla'].transform(lambda x: (x == 'SI').all())
    
    # 4. Motor de Estados Operativos
    hoy = pd.Timestamp(datetime.today().date())
    
    def asignar_estado(row):
        if row['PLANILLAS_OK']:
            return "FACTURAR"
        elif hoy > row['FECHA_MAX']:
            return "CERRADA"
        else:
            return "ABIERTA"
            
    df['ESTADO ORDEN'] = df.apply(asignar_estado, axis=1)
    
    # 5. Cálculo de Días Vencidos
    def calcular_dias(row):
        if row['ESTADO ORDEN'] == 'CERRADA':
            return (hoy - row['FECHA_MAX']).days
        elif row['ESTADO ORDEN'] == 'ABIERTA' and row['Planilla'] == 'NO':
            return (hoy - row['Fecha']).days
        return 0
        
    df['DIAS VENCIMIENTO'] = df.apply(calcular_dias, axis=1)
    
    # 6. Dashboard Visual
    col1, col2, col3 = st.columns(3)
    col1.metric("💰 OS PARA FACTURAR", df[df['ESTADO ORDEN'] == 'FACTURAR']['Numero Orden'].nunique())
    col2.metric("📂 OS ABIERTAS", df[df['ESTADO ORDEN'] == 'ABIERTA']['Numero Orden'].nunique())
    col3.metric("🔒 OS CERRADAS", df[df['ESTADO ORDEN'] == 'CERRADA']['Numero Orden'].nunique())
    
    st.divider()
    st.dataframe(df[['Numero Orden', 'Fecha', 'Planilla', 'ESTADO ORDEN', 'DIAS VENCIMIENTO']], use_container_width=True)
else:
    st.info("Esperando el archivo de Cronos para generar el dashboard...")
