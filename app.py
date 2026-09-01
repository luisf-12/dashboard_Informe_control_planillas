import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Control de Planillas", layout="wide")
st.title("🚛 Emprestur - Control de Planillas")

# 1. Botón para subir el archivo en bruto de Cronos
archivo_subido = st.file_uploader("Sube el archivo exportado de Cronos (Excel)", type=["xlsx"])

if archivo_subido:
    # 2. Lectura y Limpieza Automática (Lo que antes hacías en Excel)
    df = pd.read_excel(archivo_subido)
    
    # Limpieza de 14 caracteres
    df['ORDEN SERVICIO'] = df['ORDEN SERVICIO'].astype(str).str.strip().str[:14]
    
    # Conversión de texto a fecha real
    df['FECHA DEL SERVICIO'] = pd.to_datetime(df['FECHA DEL SERVICIO'], errors='coerce')
    
    # Calcular Fecha Máxima por Orden
    df['FECHA_MAX'] = df.groupby('ORDEN SERVICIO')['FECHA DEL SERVICIO'].transform('max')
    
    # Validar si todas las planillas de la orden dicen "SI"
    df['PLANILLAS_OK'] = df.groupby('ORDEN SERVICIO')['PLANILLA'].transform(lambda x: (x == 'SI').all())
    
    # 3. Motor de Estados Operativos
    hoy = pd.Timestamp(datetime.today().date())
    
    def asignar_estado(row):
        if row['PLANILLAS_OK']:
            return "FACTURAR"
        elif hoy > row['FECHA_MAX']:
            return "CERRADA"
        else:
            return "ABIERTA"
            
    df['ESTADO ORDEN'] = df.apply(asignar_estado, axis=1)
    
    # 4. Cálculo de Días Vencidos
    def calcular_dias(row):
        if row['ESTADO ORDEN'] == 'CERRADA':
            return (hoy - row['FECHA_MAX']).days
        elif row['ESTADO ORDEN'] == 'ABIERTA' and row['PLANILLA'] == 'NO':
            return (hoy - row['FECHA DEL SERVICIO']).days
        return 0
        
    df['DIAS VENCIMIENTO'] = df.apply(calcular_dias, axis=1)
    
    # 5. Dashboard Visual
    col1, col2, col3 = st.columns(3)
    col1.metric("💰 OS PARA FACTURAR", df[df['ESTADO ORDEN'] == 'FACTURAR']['ORDEN SERVICIO'].nunique())
    col2.metric("📂 OS ABIERTAS", df[df['ESTADO ORDEN'] == 'ABIERTA']['ORDEN SERVICIO'].nunique())
    col3.metric("🔒 OS CERRADAS", df[df['ESTADO ORDEN'] == 'CERRADA']['ORDEN SERVICIO'].nunique())
    
    st.divider()
    st.dataframe(df[['ORDEN SERVICIO', 'FECHA DEL SERVICIO', 'PLANILLA', 'ESTADO ORDEN', 'DIAS VENCIMIENTO']], use_container_width=True)
else:
    st.info("Esperando el archivo de Cronos para generar el dashboard...")