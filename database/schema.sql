--
-- PostgreSQL database dump
--

-- Dumped from database version 16.2
-- Dumped by pg_dump version 16.2

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
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


--
-- Name: alertas_hogar; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.alertas_hogar (
    id uuid NOT NULL,
    hogar_id uuid NOT NULL,
    publicacion_id uuid NOT NULL,
    creada timestamp with time zone NOT NULL,
    leida boolean NOT NULL
);


--
-- Name: eventos_auditoria; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.eventos_auditoria (
    id integer NOT NULL,
    actor_id uuid,
    action character varying(80) NOT NULL,
    entity_id character varying(80) NOT NULL,
    created_at timestamp with time zone NOT NULL
);


--
-- Name: audit_events_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.audit_events_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: audit_events_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.audit_events_id_seq OWNED BY public.eventos_auditoria.id;


--
-- Name: ejecuciones_sincronizacion; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ejecuciones_sincronizacion (
    id integer NOT NULL,
    fuente_clave character varying(80) NOT NULL,
    iniciado timestamp with time zone NOT NULL,
    finalizado timestamp with time zone,
    estado character varying(20) NOT NULL,
    nuevos integer NOT NULL,
    actualizados integer NOT NULL,
    detalle text NOT NULL
);


--
-- Name: ejecuciones_sincronizacion_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.ejecuciones_sincronizacion_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: ejecuciones_sincronizacion_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.ejecuciones_sincronizacion_id_seq OWNED BY public.ejecuciones_sincronizacion.id;


--
-- Name: fuentes_externas; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.fuentes_externas (
    clave character varying(80) NOT NULL,
    nombre character varying(120) NOT NULL,
    tipo character varying(20) NOT NULL,
    url text NOT NULL,
    intervalo_minutos integer NOT NULL,
    ultimo_intento timestamp with time zone,
    ultimo_exito timestamp with time zone,
    error text NOT NULL
);


--
-- Name: hogares; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.hogares (
    id uuid NOT NULL,
    owner_id uuid NOT NULL,
    name character varying(80) NOT NULL,
    district character varying(80) NOT NULL,
    sector character varying(120) NOT NULL,
    members integer NOT NULL,
    drinking_daily numeric(12,2),
    other_daily numeric(12,2),
    data_version integer NOT NULL,
    created_at timestamp with time zone NOT NULL,
    CONSTRAINT households_drinking_daily_check CHECK (((drinking_daily IS NULL) OR (drinking_daily >= (0)::numeric))),
    CONSTRAINT households_members_check CHECK ((members > 0)),
    CONSTRAINT households_other_daily_check CHECK (((other_daily IS NULL) OR (other_daily >= (0)::numeric)))
);


--
-- Name: limites_intentos; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.limites_intentos (
    key character varying(64) NOT NULL,
    count integer NOT NULL,
    expires_at timestamp with time zone NOT NULL
);


--
-- Name: movimientos; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.movimientos (
    id uuid NOT NULL,
    container_id uuid NOT NULL,
    actor_id uuid NOT NULL,
    kind character varying(20) NOT NULL,
    liters numeric(12,2) NOT NULL,
    balance_after numeric(12,2) NOT NULL,
    reason character varying(240) NOT NULL,
    idempotency_key character varying(80) NOT NULL,
    fingerprint character varying(64) NOT NULL,
    created_at timestamp with time zone NOT NULL,
    CONSTRAINT movements_kind_check CHECK (((kind)::text = ANY ((ARRAY['initial'::character varying, 'refill'::character varying, 'consumption'::character varying, 'adjust_up'::character varying, 'adjust_down'::character varying])::text[]))),
    CONSTRAINT movements_liters_check CHECK ((liters > (0)::numeric))
);


--
-- Name: planes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.planes (
    id uuid NOT NULL,
    household_id uuid NOT NULL,
    hours integer NOT NULL,
    data_version integer NOT NULL,
    snapshot jsonb NOT NULL,
    created_at timestamp with time zone NOT NULL,
    CONSTRAINT plans_hours_check CHECK (((hours > 0) AND (hours <= 720)))
);


--
-- Name: publicaciones_externas; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.publicaciones_externas (
    id uuid NOT NULL,
    fuente_clave character varying(80) NOT NULL,
    clave_origen character varying(64) NOT NULL,
    categoria character varying(20) NOT NULL,
    datos jsonb NOT NULL,
    hash_contenido character varying(64) NOT NULL,
    revision character varying(20) NOT NULL,
    observacion text NOT NULL,
    consultado timestamp with time zone NOT NULL,
    actualizado timestamp with time zone NOT NULL,
    CONSTRAINT publicaciones_externas_categoria_check CHECK (((categoria)::text = ANY ((ARRAY['corte'::character varying, 'punto'::character varying, 'orientacion'::character varying])::text[]))),
    CONSTRAINT publicaciones_externas_revision_check CHECK (((revision)::text = ANY ((ARRAY['automatico'::character varying, 'pendiente'::character varying, 'aprobado'::character varying, 'descartado'::character varying])::text[])))
);


--
-- Name: recipientes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.recipientes (
    id uuid NOT NULL,
    household_id uuid NOT NULL,
    name character varying(80) NOT NULL,
    water_type character varying(20) NOT NULL,
    capacity numeric(12,2) NOT NULL,
    balance numeric(12,2) NOT NULL,
    active boolean NOT NULL,
    created_at timestamp with time zone NOT NULL,
    CONSTRAINT containers_check CHECK (((capacity > (0)::numeric) AND (balance >= (0)::numeric) AND (balance <= capacity))),
    CONSTRAINT containers_water_type_check CHECK (((water_type)::text = ANY ((ARRAY['drinking'::character varying, 'other'::character varying])::text[])))
);


--
-- Name: sesiones; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sesiones (
    id uuid NOT NULL,
    user_id uuid,
    token_hash character varying(64) NOT NULL,
    csrf_token character varying(80) NOT NULL,
    created_at timestamp with time zone NOT NULL,
    last_seen timestamp with time zone NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    revoked boolean NOT NULL
);


--
-- Name: usuarios; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.usuarios (
    id uuid NOT NULL,
    name character varying(80) NOT NULL,
    email character varying(254) NOT NULL,
    password_hash text NOT NULL,
    role character varying(10) NOT NULL,
    active boolean NOT NULL,
    created_at timestamp with time zone NOT NULL,
    CONSTRAINT users_role_check CHECK (((role)::text = ANY ((ARRAY['USER'::character varying, 'ADMIN'::character varying])::text[])))
);


--
-- Name: ejecuciones_sincronizacion id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ejecuciones_sincronizacion ALTER COLUMN id SET DEFAULT nextval('public.ejecuciones_sincronizacion_id_seq'::regclass);


--
-- Name: eventos_auditoria id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.eventos_auditoria ALTER COLUMN id SET DEFAULT nextval('public.audit_events_id_seq'::regclass);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: alertas_hogar alertas_hogar_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alertas_hogar
    ADD CONSTRAINT alertas_hogar_pkey PRIMARY KEY (id);


--
-- Name: eventos_auditoria audit_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.eventos_auditoria
    ADD CONSTRAINT audit_events_pkey PRIMARY KEY (id);


--
-- Name: recipientes containers_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recipientes
    ADD CONSTRAINT containers_pkey PRIMARY KEY (id);


--
-- Name: ejecuciones_sincronizacion ejecuciones_sincronizacion_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ejecuciones_sincronizacion
    ADD CONSTRAINT ejecuciones_sincronizacion_pkey PRIMARY KEY (id);


--
-- Name: fuentes_externas fuentes_externas_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fuentes_externas
    ADD CONSTRAINT fuentes_externas_pkey PRIMARY KEY (clave);


--
-- Name: hogares households_owner_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hogares
    ADD CONSTRAINT households_owner_id_key UNIQUE (owner_id);


--
-- Name: hogares households_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hogares
    ADD CONSTRAINT households_pkey PRIMARY KEY (id);


--
-- Name: movimientos movements_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.movimientos
    ADD CONSTRAINT movements_pkey PRIMARY KEY (id);


--
-- Name: planes plans_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.planes
    ADD CONSTRAINT plans_pkey PRIMARY KEY (id);


--
-- Name: publicaciones_externas publicaciones_externas_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.publicaciones_externas
    ADD CONSTRAINT publicaciones_externas_pkey PRIMARY KEY (id);


--
-- Name: limites_intentos rate_limits_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.limites_intentos
    ADD CONSTRAINT rate_limits_pkey PRIMARY KEY (key);


--
-- Name: sesiones sessions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sesiones
    ADD CONSTRAINT sessions_pkey PRIMARY KEY (id);


--
-- Name: sesiones sessions_token_hash_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sesiones
    ADD CONSTRAINT sessions_token_hash_key UNIQUE (token_hash);


--
-- Name: alertas_hogar uq_alerta_hogar_aviso; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alertas_hogar
    ADD CONSTRAINT uq_alerta_hogar_aviso UNIQUE (hogar_id, publicacion_id);


--
-- Name: movimientos uq_movement_actor_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.movimientos
    ADD CONSTRAINT uq_movement_actor_key UNIQUE (actor_id, idempotency_key);


--
-- Name: publicaciones_externas uq_publicacion_origen; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.publicaciones_externas
    ADD CONSTRAINT uq_publicacion_origen UNIQUE (fuente_clave, clave_origen);


--
-- Name: usuarios users_email_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuarios
    ADD CONSTRAINT users_email_key UNIQUE (email);


--
-- Name: usuarios users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuarios
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: ix_alertas_hogar_hogar_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_alertas_hogar_hogar_id ON public.alertas_hogar USING btree (hogar_id);


--
-- Name: ix_movimientos_container_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_movimientos_container_id ON public.movimientos USING btree (container_id);


--
-- Name: ix_planes_household_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_planes_household_id ON public.planes USING btree (household_id);


--
-- Name: ix_publicaciones_externas_categoria; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_publicaciones_externas_categoria ON public.publicaciones_externas USING btree (categoria);


--
-- Name: ix_publicaciones_externas_fuente_clave; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_publicaciones_externas_fuente_clave ON public.publicaciones_externas USING btree (fuente_clave);


--
-- Name: ix_recipientes_household_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_recipientes_household_id ON public.recipientes USING btree (household_id);


--
-- Name: ix_sesiones_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_sesiones_user_id ON public.sesiones USING btree (user_id);


--
-- Name: alertas_hogar alertas_hogar_hogar_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alertas_hogar
    ADD CONSTRAINT alertas_hogar_hogar_id_fkey FOREIGN KEY (hogar_id) REFERENCES public.hogares(id);


--
-- Name: alertas_hogar alertas_hogar_publicacion_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alertas_hogar
    ADD CONSTRAINT alertas_hogar_publicacion_id_fkey FOREIGN KEY (publicacion_id) REFERENCES public.publicaciones_externas(id);


--
-- Name: eventos_auditoria audit_events_actor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.eventos_auditoria
    ADD CONSTRAINT audit_events_actor_id_fkey FOREIGN KEY (actor_id) REFERENCES public.usuarios(id);


--
-- Name: recipientes containers_household_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recipientes
    ADD CONSTRAINT containers_household_id_fkey FOREIGN KEY (household_id) REFERENCES public.hogares(id);


--
-- Name: ejecuciones_sincronizacion ejecuciones_sincronizacion_fuente_clave_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ejecuciones_sincronizacion
    ADD CONSTRAINT ejecuciones_sincronizacion_fuente_clave_fkey FOREIGN KEY (fuente_clave) REFERENCES public.fuentes_externas(clave);


--
-- Name: hogares households_owner_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hogares
    ADD CONSTRAINT households_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES public.usuarios(id);


--
-- Name: movimientos movements_actor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.movimientos
    ADD CONSTRAINT movements_actor_id_fkey FOREIGN KEY (actor_id) REFERENCES public.usuarios(id);


--
-- Name: movimientos movements_container_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.movimientos
    ADD CONSTRAINT movements_container_id_fkey FOREIGN KEY (container_id) REFERENCES public.recipientes(id);


--
-- Name: planes plans_household_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.planes
    ADD CONSTRAINT plans_household_id_fkey FOREIGN KEY (household_id) REFERENCES public.hogares(id);


--
-- Name: publicaciones_externas publicaciones_externas_fuente_clave_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.publicaciones_externas
    ADD CONSTRAINT publicaciones_externas_fuente_clave_fkey FOREIGN KEY (fuente_clave) REFERENCES public.fuentes_externas(clave);


--
-- Name: sesiones sessions_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sesiones
    ADD CONSTRAINT sessions_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.usuarios(id);


--
-- PostgreSQL database dump complete
--

