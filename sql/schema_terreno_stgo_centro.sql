-- Esquema operativo DepaFix Santiago Centro
-- Generado desde operacion_terreno/db.py (SQLAlchemy)

CREATE TABLE inspecciones_terreno (
	id SERIAL NOT NULL, 
	propiedad_id VARCHAR(32) NOT NULL, 
	direccion VARCHAR(255) NOT NULL, 
	departamento VARCHAR(32), 
	torre VARCHAR(16), 
	comuna VARCHAR(80) DEFAULT 'Santiago' NOT NULL, 
	bloque VARCHAR(32), 
	segmento_ruta VARCHAR(16), 
	parada_ruta INTEGER, 
	fecha_inspeccion TIMESTAMP WITH TIME ZONE, 
	inspector VARCHAR(120), 
	estado_visita VARCHAR(12) DEFAULT 'PENDIENTE' NOT NULL, 
	tipo_agua_caliente VARCHAR(15) DEFAULT 'SIN_INFORMACION' NOT NULL, 
	fecha_ultima_mantencion_termo DATE, 
	fecha_proxima_mantencion_termo DATE, 
	intervalo_mantencion_meses INTEGER, 
	requiere_piso_spc BOOLEAN DEFAULT false NOT NULL, 
	m2_piso_spc NUMERIC(8, 2), 
	plafones_led INTEGER DEFAULT 0 NOT NULL, 
	enchufes INTEGER DEFAULT 0 NOT NULL, 
	soporte_tv INTEGER DEFAULT 0 NOT NULL, 
	fotos_antes JSONB NOT NULL, 
	fotos_despues JSONB NOT NULL, 
	videos_antes JSONB NOT NULL, 
	videos_despues JSONB NOT NULL, 
	observaciones TEXT, 
	latitud NUMERIC(10, 6), 
	longitud NUMERIC(10, 6), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_inspeccion_intervalo_mantencion CHECK (intervalo_mantencion_meses IS NULL OR intervalo_mantencion_meses IN (6, 12)), 
	CONSTRAINT ck_inspeccion_m2_spc CHECK (m2_piso_spc IS NULL OR m2_piso_spc >= 0), 
	CONSTRAINT ck_inspeccion_plafones CHECK (plafones_led >= 0), 
	CONSTRAINT ck_inspeccion_enchufes CHECK (enchufes >= 0), 
	CONSTRAINT ck_inspeccion_soporte_tv CHECK (soporte_tv >= 0), 
	CONSTRAINT estado_visita CHECK (estado_visita IN ('PENDIENTE', 'REALIZADA', 'NO_ACCESO', 'REPROGRAMADA', 'CANCELADA', 'NO_APLICA')), 
	CONSTRAINT tipo_agua_caliente CHECK (tipo_agua_caliente IN ('TERMO_ELECTRICO', 'CALEFONT', 'CALDERA_CENTRAL', 'SIN_INFORMACION'))
);
CREATE INDEX ix_inspecciones_terreno_propiedad_id ON inspecciones_terreno (propiedad_id);

CREATE TABLE log_comunicaciones_corredor (
	id SERIAL NOT NULL, 
	propiedad_id VARCHAR(32) NOT NULL, 
	inspeccion_id INTEGER, 
	canal VARCHAR(10) NOT NULL, 
	direccion VARCHAR(8) DEFAULT 'SALIENTE' NOT NULL, 
	estado_contacto VARCHAR(13) DEFAULT 'PENDIENTE' NOT NULL, 
	fecha_contacto TIMESTAMP WITH TIME ZONE, 
	mensaje TEXT, 
	proximo_seguimiento TIMESTAMP WITH TIME ZONE, 
	responsable VARCHAR(120), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(inspeccion_id) REFERENCES inspecciones_terreno (id) ON DELETE SET NULL, 
	CONSTRAINT canal_comunicacion CHECK (canal IN ('WHATSAPP', 'LLAMADA', 'EMAIL', 'PRESENCIAL')), 
	CONSTRAINT direccion_comunicacion CHECK (direccion IN ('SALIENTE', 'ENTRANTE')), 
	CONSTRAINT estado_contacto CHECK (estado_contacto IN ('PENDIENTE', 'ENVIADO', 'RESPONDIDO', 'SIN_RESPUESTA', 'AGENDADO', 'RECHAZADO', 'CERRADO'))
);
CREATE INDEX ix_log_comunicaciones_corredor_inspeccion_id ON log_comunicaciones_corredor (inspeccion_id);
CREATE INDEX ix_log_comunicaciones_corredor_propiedad_id ON log_comunicaciones_corredor (propiedad_id);

CREATE TABLE presupuestos_obra (
	id SERIAL NOT NULL, 
	inspeccion_id INTEGER NOT NULL, 
	propiedad_id VARCHAR(32) NOT NULL, 
	fecha_emision DATE, 
	estado VARCHAR(9) DEFAULT 'BORRADOR' NOT NULL, 
	moneda VARCHAR(8) DEFAULT 'CLP' NOT NULL, 
	neto NUMERIC(12, 2) DEFAULT 0 NOT NULL, 
	iva NUMERIC(12, 2) DEFAULT 0 NOT NULL, 
	total NUMERIC(12, 2) DEFAULT 0 NOT NULL, 
	partidas JSONB NOT NULL, 
	pdf_path VARCHAR(500), 
	observaciones TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_presupuesto_neto CHECK (neto >= 0), 
	CONSTRAINT ck_presupuesto_iva CHECK (iva >= 0), 
	CONSTRAINT ck_presupuesto_total CHECK (total >= 0), 
	FOREIGN KEY(inspeccion_id) REFERENCES inspecciones_terreno (id) ON DELETE CASCADE, 
	CONSTRAINT estado_presupuesto CHECK (estado IN ('BORRADOR', 'ENVIADO', 'APROBADO', 'RECHAZADO', 'VENCIDO'))
);
CREATE INDEX ix_presupuestos_obra_inspeccion_id ON presupuestos_obra (inspeccion_id);
CREATE INDEX ix_presupuestos_obra_propiedad_id ON presupuestos_obra (propiedad_id);

