import streamlit as st
import pandas as pd
from datetime import datetime
import io

st.set_page_config(page_title="Control de Planillas", layout="wide")
st.title(" Emprestur - Dashboard de Control - Sura Pacientes")

# --- 1. CONFIGURACIÓN DE LA FUENTE DE DATOS HÍBRIDA ---
URL_ONEDRIVE = "https://emprestur-my.sharepoint.com/:x:/p/luis_chaverra/IQCniaGiK1XrR6dzDOreyyoDARDlHVTBFIEYS4tsCMbHxOY?download=1"

st.sidebar.markdown("**Herramienta Operativa**")
archivo_subido = st.sidebar.file_uploader("Auxiliar: Carga un corte temporal aquí (Opcional)", type=["xlsx"])

try:
    # --- 2. DECISIÓN DE LECTURA (JEFA VS AUXILIAR) ---
    if archivo_subido is not None:
        df = pd.read_excel(archivo_subido)
        st.success("📂 Visualizando corte temporal cargado manualmente.")
    else:
        df = pd.read_excel(URL_ONEDRIVE)
        st.caption("☁️ Visualizando la base oficial sincronizada desde OneDrive.")

    # --- 3. LIMPIEZA Y TRANSFORMACIÓN DE DATOS ---
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
    
    # --- 4. INTERFAZ DEL DASHBOARD ---
    st.sidebar.markdown("**Filtros de Búsqueda**")
    filtro_estado = st.sidebar.multiselect("ESTADO ORDEN:", options=df['ESTADO ORDEN'].unique(), default=df['ESTADO ORDEN'].unique())
    filtro_planilla = st.sidebar.multiselect("ESTADO PLANILLA:", options=df['ESTADO PLANILLA'].unique(), default=df['ESTADO PLANILLA'].unique())
    
    max_dias = int(df['DIAS_NUM'].max()) if not df['DIAS_NUM'].empty else 0
    filtro_dias = st.sidebar.slider("Mínimo de días vencidos:", min_value=0, max_value=max_dias, value=0)
    
    df_filtrado = df[
        (df['ESTADO ORDEN'].isin(filtro_estado)) & 
        (df['ESTADO PLANILLA'].isin(filtro_planilla)) &
        (df['DIAS_NUM'] >= filtro_dias)
    ]
    
    # --- BLOQUE 1: KPIs POR ÓRDENES ÚNICAS ---
    st.markdown("**Resumen General por Órdenes Únicas**")
    total_ordenes = df_filtrado['Numero Orden'].nunique()
    ord_facturar = df_filtrado[df_filtrado['ESTADO ORDEN'] == 'FACTURAR']['Numero Orden'].nunique()
    ord_abiertas = df_filtrado[df_filtrado['ESTADO ORDEN'] == 'ABIERTA']['Numero Orden'].nunique()
    ord_cerradas = df_filtrado[df_filtrado['ESTADO ORDEN'] == 'CERRADA']['Numero Orden'].nunique()
    
    pct_ord_facturar = (ord_facturar / total_ordenes * 100) if total_ordenes > 0 else 0
    pct_ord_abiertas = (ord_abiertas / total_ordenes * 100) if total_ordenes > 0 else 0
    pct_ord_cerradas = (ord_cerradas / total_ordenes * 100) if total_ordenes > 0 else 0
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("📊 TOTAL ÓRDENES", total_ordenes)
    col2.metric(" ORDEN PARA FACTURAR", ord_facturar, f"{pct_ord_facturar:.1f}% del total", delta_color="off")
    col3.metric(" ÓRDENES ABIERTAS", ord_abiertas, f"{pct_ord_abiertas:.1f}% del total", delta_color="off")
    col4.metric(" ÓRDENES CERRADAS", ord_cerradas, f"{pct_ord_cerradas:.1f}% del total", delta_color="off")
    
    st.divider()
    
    # --- BLOQUE 2: KPIs POR SERVICIOS (VIAJES) ---
    st.markdown("**Resumen Operativo por Servicios (Viajes Individuales)**")
    total_servicios = len(df_filtrado)
    serv_facturar = len(df_filtrado[df_filtrado['ESTADO ORDEN'] == 'FACTURAR'])
    serv_abiertas = len(df_filtrado[df_filtrado['ESTADO ORDEN'] == 'ABIERTA'])
    serv_cerradas = len(df_filtrado[df_filtrado['ESTADO ORDEN'] == 'CERRADA'])
    
    pct_serv_facturar = (serv_facturar / total_servicios * 100) if total_servicios > 0 else 0
    pct_serv_abiertas = (serv_abiertas / total_servicios * 100) if total_servicios > 0 else 0
    pct_serv_cerradas = (serv_cerradas / total_servicios * 100) if total_servicios > 0 else 0
    
    col5, col6, col7, col8 = st.columns(4)
    col5.metric("🚚 TOTAL SERVICIOS", total_servicios)
    col6.metric(" OS PARA FACTURAR", serv_facturar, f"{pct_serv_facturar:.1f}% del total", delta_color="off")
    col7.metric(" OS ABIERTAS", serv_abiertas, f"{pct_serv_abiertas:.1f}% del total", delta_color="off")
    col8.metric(" OS CERRADAS", serv_cerradas, f"{pct_serv_cerradas:.1f}% del total", delta_color="off")
    
    st.divider()
    
    # --- BLOQUE 3: DESGLOSE POR ESTADO DE PLANILLA ---
    st.markdown("**Desglose de Servicios por Estado de Planilla**")
    if total_servicios > 0:
        df_desglose = df_filtrado.groupby('ESTADO PLANILLA').size().reset_index(name='Cantidad de Servicios')
        df_desglose['Porcentaje del Total'] = (df_desglose['Cantidad de Servicios'] / total_servicios * 100).map("{:.1f}%".format)
        st.dataframe(df_desglose, use_container_width=True, hide_index=True)
    else:
        st.info("No hay servicios para mostrar con los filtros actuales.")
        
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
    
    # --- BOTÓN DE DESCARGA EXCEL ---
    def convertir_df_a_excel(df_exportar):
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_exportar.to_excel(writer, index=False, sheet_name='Servicios_Filtrados')
        return output.getvalue()
        
    datos_excel = convertir_df_a_excel(df_mostrar)
    
    st.download_button(
        label="📥 Descargar tabla (.xlsx)",
        data=datos_excel,
        file_name=f"Reporte_Planillas_{datetime.now().strftime('%d-%m-%Y')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

except Exception as e:
    st.error(f"Error al cargar la base de datos. Si eres la gerencia, valida que el auxiliar haya guardado el archivo oficial en OneDrive. Detalle técnico: {e}")
