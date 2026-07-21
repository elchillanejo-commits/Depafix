--
-- PostgreSQL database dump
--

\restrict Wjq7Nt1AHAKAX4DjMpNzlm0IgAPFz58908WzZwYayIDZPhJmQCedcZ3wbDFE1Ro

-- Dumped from database version 16.14 (Ubuntu 16.14-0ubuntu0.24.04.1)
-- Dumped by pg_dump version 16.14 (Ubuntu 16.14-0ubuntu0.24.04.1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: solana_analysis; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.solana_analysis (
    id integer NOT NULL,
    metric_category character varying(50),
    metric_name character varying(100),
    metric_value text,
    metric_numeric numeric(20,4),
    unit character varying(20),
    context text,
    source_timestamp timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.solana_analysis OWNER TO postgres;

--
-- Name: solana_analysis_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.solana_analysis_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.solana_analysis_id_seq OWNER TO postgres;

--
-- Name: solana_analysis_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.solana_analysis_id_seq OWNED BY public.solana_analysis.id;


--
-- Name: solana_analysis id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.solana_analysis ALTER COLUMN id SET DEFAULT nextval('public.solana_analysis_id_seq'::regclass);


--
-- Data for Name: solana_analysis; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.solana_analysis (id, metric_category, metric_name, metric_value, metric_numeric, unit, context, source_timestamp) FROM stdin;
1	Bitcoin	Precio actual (referencia)	$60,000	60000.0000	USD	Precio desde el cual Bitcoin podría recuperarse hacia 85k	2026-07-19 00:27:01.850902
2	Bitcoin	Objetivo mínimo post-recuperación	$85,000	85000.0000	USD	Mínimo esperado tras superar los 60k en el próximo ciclo alcista	2026-07-19 00:27:01.850902
3	Bitcoin	Precio realizado del operador de largo plazo (LTH)	$49,000	49000.0000	USD	Nivel clave que suele perderse en los mínimos de ciclo; zona de compra	2026-07-19 00:27:01.850902
4	Bitcoin	Posible zona de mechazo (capitulación final)	$44,000 - $47,000	\N	USD	Rango estimado para el último coletazo bajista antes de revertir	2026-07-19 00:27:01.850902
5	On-Chain	Holders de largo plazo (LTH) - tendencia	Aumentando tenencias	\N	\N	Línea azul: los operadores de largo plazo están acumulando en zonas bajas	2026-07-19 00:27:01.850902
6	On-Chain	Nuevo dinero entrante (STH) - tendencia	En mínimos de varios años	\N	\N	Línea roja: el interés de nuevo capital está en niveles de fondo de ciclo	2026-07-19 00:27:01.850902
7	On-Chain	Sentimiento del LTH (índice de miedo)	En miedo, sin llegar a punto cero	\N	\N	Falta la capitulación final del LTH para confirmar el mínimo absoluto	2026-07-19 00:27:01.850902
8	Sentimiento	Interés general en Bitcoin	En niveles de mínimos de 2011, 2015 y 2018	\N	\N	Métrica compuesta que indica desinterés propio de zonas de acumulación	2026-07-19 00:27:01.850902
9	Sentimiento	Miedo / codicia (Fear & Greed)	Miedo	\N	\N	Indicador en zona de miedo, aún no en pánico extremo	2026-07-19 00:27:01.850902
10	Estrategia	Zona de compra (alta probabilidad)	Por debajo de $49,000	49000.0000	USD	Precio realizado del LTH; históricamente mejor zona de compra del ciclo	2026-07-19 00:27:01.850902
11	Estrategia	Capitulación final esperada	Pérdida del nivel $49,000 y sentimiento LTH en negativo	\N	\N	Condición necesaria para que los mínimos sean duraderos	2026-07-19 00:27:01.850902
12	Estrategia	Estructura de mercado actual	Cambio de dinámica: de limpiar cortos a limpiar largos	\N	\N	Indica que las élites están preparando el terreno para el próximo rally	2026-07-19 00:27:01.850902
13	Escenario	Escenario base (alcista)	Bitcoin a $85,000 como mínimo tras recuperar $60,000	85000.0000	USD	Movimiento esperado para el segundo trimestre de 2027	2026-07-19 00:27:01.850902
14	Escenario	Escenario de capitulación final	Mechazo a $44k-$47k, luego recuperación violenta	\N	USD	Manipulación típica antes de revertir la tendencia bajista	2026-07-19 00:27:01.850902
15	Escenario	Punto líquido más importante (liquidez bajista)	$49,000	49000.0000	USD	Nivel donde se concentran órdenes de stop-loss; probablemente será cazado	2026-07-19 00:27:01.850902
16	Análisis Técnico	Patrón actual	Acumulación → Manipulación → Expansión (WOF)	\N	\N	Estructura cíclica que precede a grandes movimientos alcistas	2026-07-19 00:27:01.850902
17	Análisis Técnico	Estructura correctiva en Ethereum	Flat (3-3-5) en zona de resistencia	\N	\N	Indica que ETH probablemente buscará mínimos por debajo de $1700	2026-07-19 00:27:01.850902
18	Conclusión	¿Comprar ahora?	Sí, en zona de acumulación, pero no el mínimo	\N	\N	Las élites están comprando silenciosamente; falta la capitulación final	2026-07-19 00:27:01.850902
19	Conclusión	Recomendación final	Acumular en DCA por debajo de $49k, guardar liquidez para mechazo a $44k-$47k	\N	\N	Estrategia para maximizar entrada en el próximo bullrun 2027-2028	2026-07-19 00:27:01.850902
\.


--
-- Name: solana_analysis_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.solana_analysis_id_seq', 19, true);


--
-- Name: solana_analysis solana_analysis_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.solana_analysis
    ADD CONSTRAINT solana_analysis_pkey PRIMARY KEY (id);


--
-- PostgreSQL database dump complete
--

\unrestrict Wjq7Nt1AHAKAX4DjMpNzlm0IgAPFz58908WzZwYayIDZPhJmQCedcZ3wbDFE1Ro

