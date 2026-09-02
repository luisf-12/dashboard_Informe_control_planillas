import os
import io
import pandas as pd
import streamlit as st

# --- CONFIGURACIÓN Y POLÍTICA DE RETENCIÓN ---
CARPETA_HISTORIAL = "historial_archivos"
LIMITE_HISTORIAL = 5

if not os.path.exists(CARPETA_HISTORIAL):
    os.makedirs(CARPETA_HISTORIAL)

def aplicar_politica_retencion(carpeta, limite):
    archivos = [f for f in os.listdir(carpeta) if f.endswith(".xlsx")]
    archivos_ordenados = sorted(archivos, reverse=True)
    
    if len(archivos_ordenados) > limite:
        for archivo in archivos_ordenados[limite:]:
            try:
                os.remove(os.path.join(carpeta, archivo))
            except OSError:
                pass

st.set_page_config(page_title="Control de Planillas", layout="wide")
st.title("📊 Emprestur - Dashboard de Control - Sura Pacientes")

# --- CARGADOR PRINCIPAL (CENTRO/ARRIBA) ---
archivo_subido = st.file_uploader("Sube el archivo exportado de Cronos (Excel)", type=["xlsx"])

if archivo_subido is not None:
    # Uso del motor de Pandas para forzar la hora de Colombia de forma estricta
    ahora = pd.Timestamp.now(tz='America/Bogota')
    timestamp = ahora.strftime("%Y%m%d_%H%M%S")
    nombre_guardado = f"Cronos_Reporte_{timestamp}.xlsx"
    ruta_guardado = os.path.join(CARPETA_HISTORIAL, nombre_guardado)
    
    with open(ruta_guardado, "wb") as f:
        f.write(archivo_subido.getbuffer())
        
    aplicar_politica_retencion(CARPETA_HISTORIAL, LIMITE_HISTORIAL)
    st.success("Reporte guardado exitosamente. Selecciona la nueva versión en el historial.")
    st.rerun()

# --- ESTRUCTURA VISUAL DEL PANEL LATERAL ---
st.sidebar.markdown("**🔍 Filtros de Búsqueda**")
contenedor_filtros = st.sidebar.container()

st.sidebar.markdown("<br><br><br><br>", unsafe_allow_html=True) 
st.sidebar.divider()

contenedor_historial = st.sidebar.container()
contenedor_historial.markdown("**📂 Historial de Reportes**")

archivos_disponibles = sorted(
    [f for f in os.listdir(CARPETA_HISTORIAL) if f.endswith(".xlsx")], 
    reverse=True
)

def formatear_nombre_reporte(nombre_archivo):
    try:
        parte_fecha = nombre_archivo.replace("Cronos_Reporte_", "").replace(".xlsx", "")
        # Parseo directo con Pandas
        dt = pd.to_datetime(parte_fecha, format="%Y%m%d_%H%M%S")
        formato = dt.strftime("%d/%m/%Y — %I:%M %p")
        
        if nombre_archivo == archivos_disponibles[0]:
            return f"🟢 {formato} (Más reciente)"
        return f"📄 {formato}"
    except Exception:
        return nombre_archivo

# --- PROCESAMIENTO Y DASHBOARD ---
if archivos_disponibles:
    archivo_seleccionado = contenedor_historial.selectbox(
        "Selecciona el reporte a visualizar:", 
        options=archivos_disponibles,
        index=0,
        format_func=formatear_nombre_reporte,
        label_visibility="collapsed"
    )
    
    ruta_leer = os.path.join(CARPETA_HISTORIAL, archivo_seleccionado)
    df = pd.read_excel(ruta_leer)
    
    df['Numero Orden'] = df['Numero Orden'].astype(str).str.strip().str[:14]
    df['Fecha'] = pd.to_datetime(df['Fecha'].astype(str).str.strip(), dayfirst=True, errors='coerce')
    df['Planilla'] = df['Planilla'].astype(str).str.strip().str.upper()
    df['CANTIDAD VIAJES'] = df.groupby('Numero Orden')['Numero Orden'].transform('count')
    df['FECHA_MAX'] = df.groupby('Numero Orden')['Fecha'].transform('max')
    df['PLANILLAS_OK'] = df.groupby('Numero Orden')['Planilla'].transform(lambda x: (x == 'SI').all())
    
    # Hora local para evaluar las reglas operativas de estados
    hoy = pd.Timestamp.now(tz='America/Bogota').normalize()
    
    def asignar_estado_orden(row):
        if row['PLANILLAS_OK']:
            return "FACTURAR"
        elif pd.notnull(row['FECHA_MAX']) and hoy > row['FECHA_MAX']:
            return "CERRADA"
        else:
            return "ABIERTA"
            
    df['ESTADO ORDEN'] = df.apply(asignar_estado_orden, axis=1)
    
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
    
    # --- RENDERIZADO DE FILTROS ---
    filtro_estado = contenedor_filtros.multiselect("ESTADO ORDEN:", options=df['ESTADO ORDEN'].unique(), default=df['ESTADO ORDEN'].unique())
    filtro_planilla = contenedor_filtros.multiselect("ESTADO PLANILLA:", options=df['ESTADO PLANILLA'].unique(), default=df['ESTADO PLANILLA'].unique())
    
    max_dias = int(df['DIAS_NUM'].max()) if not df['DIAS_NUM'].empty else 0
    filtro_dias = contenedor_filtros.slider("Mínimo de días vencidos:", min_value=0, max_value=max_dias, value=0)
    
    df_filtrado = df[
        (df['ESTADO ORDEN'].isin(filtro_estado)) & 
        (df['ESTADO PLANILLA'].isin(filtro_planilla)) &
        (df['DIAS_NUM'] >= filtro_dias)
    ]
    
    # --- KPIs Y TABLAS PRINCIPALES ---
    st.divider()
    st.markdown(f"**Resumen General por Órdenes Únicas**")
    
    total_ordenes = df_filtrado['Numero Orden'].nunique()
    ord_facturar = df_filtrado[df_filtrado['ESTADO ORDEN'] == 'FACTURAR']['Numero Orden'].nunique()
    ord_abiertas = df_filtrado[df_filtrado['ESTADO ORDEN'] == 'ABIERTA']['Numero Orden'].nunique()
    ord_cerradas = df_filtrado[df_filtrado['ESTADO ORDEN'] == 'CERRADA']['Numero Orden'].nunique()
    
    pct_ord_facturar = (ord_facturar / total_ordenes * 100) if total_ordenes > 0 else 0
    pct_ord_abiertas = (ord_abiertas / total_ordenes * 100) if total_ordenes > 0 else 0
    pct_ord_cerradas = (ord_cerradas / total_ordenes * 100) if total_ordenes > 0 else 0
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("📊 TOTAL ÓRDENES", total_ordenes)
    col2.metric("✅ ORDEN PARA FACTURAR", ord_facturar, f"{pct_ord_facturar:.1f}% del total", delta_color="off")
    col3.metric("⏳ ÓRDENES ABIERTAS", ord_abiertas, f"{pct_ord_abiertas:.1f}% del total", delta_color="off")
    col4.metric("🔒 ÓRDENES CERRADAS", ord_cerradas, f"{pct_ord_cerradas:.1f}% del total", delta_color="off")
    
    st.divider()
    
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
    col6.metric("✅ OS PARA FACTURAR", serv_facturar, f"{pct_serv_facturar:.1f}% del total", delta_color="off")
    col7.metric("⏳ OS ABIERTAS", serv_abiertas, f"{pct_serv_abiertas:.1f}% del total", delta_color="off")
    col8.metric("🔒 OS CERRADAS", serv_cerradas, f"{pct_serv_cerradas:.1f}% del total", delta_color="off")
    
    st.divider()
    
    st.markdown("**Desglose de Servicios por Estado de Planilla**")
    if total_servicios > 0:
        df_desglose = df_filtrado.groupby('ESTADO PLANILLA').size().reset_index(name='Cantidad de Servicios')
        df_desglose['Porcentaje del Total'] = (df_desglose['Cantidad de Servicios'] / total_servicios * 100).map("{:.1f}%".format)
        st.dataframe(df_desglose, use_container_width=True, hide_index=True)
    else:
        st.info("No hay servicios para mostrar con los filtros actuales.")
        
    st.divider()
    
    st.markdown("**Detalle Operativo de Servicios**")
    columnas_base = ['Numero Orden', 'Paciente', 'Fecha', 'Vehiculo', 'TIPO', 'ESTADO PLANILLA', 'DIAS VENCIMIENTO']
    columnas_existentes = [col for col in columnas_base if col in df_filtrado.columns]
    
    df_mostrar = df_filtrado[columnas_existentes].copy()
    
    renombres = {
        'Numero Orden': 'ORDEN SERVICIO',
        'Paciente': 'PACIENTE',
        'Fecha': 'FECHA DEL SERVICIO',
        'Vehiculo': 'VEHICULO',
        'TIPO': 'TIPO'
    }
    df_mostrar.rename(columns={k: v for k, v in renombres.items() if k in df_mostrar.columns}, inplace=True)
    
    if 'FECHA DEL SERVICIO' in df_mostrar.columns:
        df_mostrar['FECHA DEL SERVICIO'] = df_mostrar['FECHA DEL SERVICIO'].dt.strftime('%d/%m/%Y')
    
    st.dataframe(df_mostrar, use_container_width=True, hide_index=True)
    
    def convertir_df_a_excel(df_exportar):
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_exportar.to_excel(writer, index=False, sheet_name='Servicios_Filtrados')
        return output.getvalue()
        
    datos_excel = convertir_df_a_excel(df_mostrar)
    
    st.download_button(
        label="📥 Descargar tabla filtrada (.xlsx)",
        data=datos_excel,
        file_name=f"Reporte_Planillas_{pd.Timestamp.now(tz='America/Bogota').strftime('%d-%m-%Y')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

else:
    st.info("Aún no hay datos. Sube el primer archivo de Cronos para generar el dashboard.")
