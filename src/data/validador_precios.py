import pandas as pd
import numpy as np

def validar_precios_scrapeados(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    
    df['fecha_scrapeo'] = pd.to_datetime(df['fecha_scrapeo'])
    df = df.sort_values(by=['producto_id', 'fecha_scrapeo']).reset_index(drop=True)
    
    # Regla 1
    r1_invalido = (df['precio_neto'] <= 0) | (df['precio_neto'] > 10000000)
    
    # Regla 2
    ratio_iva = df['precio_lista'] / df['precio_neto']
    r2_invalido = (ratio_iva < 1.18) | (ratio_iva > 1.20)
    
    # Regla 3
    df['precio_ayer'] = df.groupby('producto_id')['precio_neto'].shift(1)
    variacion_diaria = (df['precio_neto'] - df['precio_ayer']).abs() / df['precio_ayer']
    r3_invalido = variacion_diaria > 0.50
    
    # Regla 4
    df_temp = df.set_index('fecha_scrapeo')
    mediana_30d = df_temp.groupby('producto_id')['precio_neto'].rolling('30D').median().reset_index(drop=True)
    df['mediana_30d'] = mediana_30d.values
    
    variacion_tendencia = (df['precio_neto'] - df['mediana_30d']).abs() / df['mediana_30d']
    r4_invalido = variacion_tendencia > 0.40
    
    # Validación final
    df['es_valido'] = ~(r1_invalido | r2_invalido | r3_invalido | r4_invalido)
    df = df.drop(columns=['precio_ayer', 'mediana_30d'])
    return df
