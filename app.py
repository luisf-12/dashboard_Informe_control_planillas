import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Control de Planillas", layout="wide")
st.title("🚛 Emprestur - Dashboard de Planillas")

archivo_subido = st.file_uploader("Sube el archivo exportado de Cronos (Excel)", type=["xlsx"])

if archivo_subido:
    df = pd.read_excel(archivo_subido)
    
    # 1. Limpieza a 14 caracteres
    df['Numero Orden'] = df['Numero Orden'].astype(str).str.strip().str[:14]
    
    # Asegurar formato de fechas y limpieza
    df['Fecha'] = pd.to_datetime(df['Fecha'].astype(str).str.strip(), dayfirst=True, errors='coerce')
    df['Planilla'] = df['Planilla'].astype(str).str.strip().str.upper()
    
    # 2. Cantidad de Viajes
    df['CANTIDAD VIAJES'] = df.groupby('Numero Orden')['Numero Orden'].transform('count')
    
    # 3. Estado de la Orden
    df['FECHA_MAX'] = df.groupby('Numero Orden')['Fecha'].transform('max')
    df['PLANILLAS_OK'] = df.groupby('Numero Orden')['Planilla'].transform(lambda x: (x == 'SI').all())
    
    hoy = pd.Timestamp(datetime.today().date())
    
    def asignar_estado_orden(row):
        if row['PLANILLAS_OK']:
            return "FACTURAR"
        elif pd.notnull(row['FECHA_MAX']) and hoy > row['FECHA_MAX']:
            return "CERRADA"
        else:
            return "ABIERTA"
            
    df['ESTADO ORDEN'] = df.apply(asignar_estado_orden, axis=1)
    
    # 4. Días Vencimiento
    def calcular_dias_numericos(row):
        if row['ESTADO ORDEN'] == 'CERRADA':
            return (hoy - row['FECHA_MAX']).days if pd.notnull(row['FECHA_MAX']) else 0
        elif row['ESTADO ORDEN'] == 'ABIERTA' and row['Planilla'] == 'NO':
            return (hoy - row['Fecha']).days if pd.notnull(row['Fecha']) else 0
        return 0
        
    df['DIAS_NUM'] = df.apply(calcular_dias_numericos, axis=1)
    
    def mostrar_dias_vencimiento(row):
        if row['ESTADO ORDEN'] == 'CERRADA' or (row['ESTADO ORDEN'] == 'ABIERTA' and row['Planilla'] == 'NO'):
            return str(row['DIAS_NUM'])
        return "AL DÍA"
        
    df['DIAS VENCIMIENTO'] = df.apply(mostrar_dias_vencimiento, axis=1)
    
    # 5. Estado de la Planilla
    def asignar_estado_planilla(row):
        if row['ESTADO ORDEN'] == 'FACTURAR':
            return "FACTURAR"
        elif row['Planilla'] == 'SI':
            return "ENTREGADA"
        elif row['ESTADO ORDEN'] == 'ABIERTA':
            dias_individual = (hoy - row['Fecha']).days if pd.notnull(row['Fecha']) else 0
            return "RETRASADA" if dias_individual > 5 else "A TIEMPO"
        elif row['ESTADO ORDEN'] == 'CERRADA':
            return "RETRASADA" if row['DIAS_NUM'] > 5 else "A TIEMPO"
        return "-"
        
    df['ESTADO PLANILLA'] = df.apply(asignar_estado_planilla, axis=1)
    
    # --- INTERFAZ DEL DASHBOARD ---
    
    st.sidebar.markdown("**Filtros de Búsqueda**")
    filtro_estado = st.sidebar.multiselect("ESTADO ORDEN:", options=df['ESTADO ORDEN'].unique(), default=df['ESTADO ORDEN'].unique())
    filtro_planilla = st.sidebar.multiselect("ESTADO PLANILLA:", options=df['ESTADO PLANILLA'].unique(), default=df['ESTADO PLANILLA'].unique())
    
    # Filtro deslizante inteligente para aislar los casos críticos
    max_dias = int(df['DIAS_NUM'].max()) if not df['DIAS_NUM'].empty else 0
    filtro_dias = st.sidebar.slider("Mínimo de días vencidos:", min_value=0, max_value=max_dias, value=0)
    
    # Aplicar todos los filtros simultáneamente
    df_filtrado = df[
        (df['ESTADO ORDEN'].isin(filtro_estado)) & 
        (df['ESTADO PLANILLA'].isin(filtro_planilla)) &
        (df['DIAS_NUM'] >= filtro_dias)
    ]
    
    # KPIs
    col1, col2, col3 = st.columns(3)
    col1.metric("💰 OS PARA FACTURAR", df_filtrado[df_filtrado['ESTADO ORDEN'] == 'FACTURAR']['Numero Orden'].nunique())
    col2.metric("📂 OS ABIERTAS", df_filtrado[df_filtrado['ESTADO ORDEN'] == 'ABIERTA']['Numero Orden'].nunique())
    col3.metric("🔒 OS CERRADAS", df_filtrado[df_filtrado['ESTADO ORDEN'] == 'CERRADA']['Numero Orden'].nunique())
    
    st.divider()
    
    # --- TABLA DETALLADA ---
    st.markdown("**Detalle Operativo de Servicios**")
    
    columnas_base = ['Numero Orden', 'Paciente', 'Fecha', 'Vehiculo', 'TIPO', 'ESTADO PLANILLA', 'DIAS VENCIMIENTO']
    df_mostrar = df_filtrado[columnas_base].copy()
    
    df_mostrar.rename(columns={
        'Numero Orden': 'ORDEN SERVICIO',
        'Paciente': 'PACIENTE',
        'Fecha': 'FECHA DEL SERVICIO',
        'Vehiculo': 'VEHICULO',
        'TIPO': 'TIPO'
    }, inplace=True)
    
    df_mostrar['FECHA DEL SERVICIO'] = df_mostrar['FECHA DEL SERVICIO'].dt.strftime('%d/%m/%Y')
    
    st.dataframe(df_mostrar, use_container_width=True, hide_index=True)

else:
    st.info("Esperando el archivo de Cronos para generar el dashboard...")
