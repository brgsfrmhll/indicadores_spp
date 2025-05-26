import schedule
import time
import threading
import streamlit as st
import os
import re
import json
import hashlib
import pandas as pd
from datetime import datetime, timedelta
import base64
from io import BytesIO
import plotly.express as px
import locale
from cryptography.fernet import Fernet
from pathlib import Path
from sympy import symbols, sympify, SympifyError
from streamlit_scroll_to_top import scroll_to_here

# --- Importações e configurações do PostgreSQL ---
import psycopg2
from psycopg2 import sql
from psycopg2.extras import Json # Para lidar com JSONB

KEY_FILE = "secret.key"

# --- Funções de Conexão e Criação de Tabelas do PostgreSQL ---

def get_db_connection():
    """
    Estabelece e retorna uma conexão com o banco de dados PostgreSQL.
    """
    try:
        conn = psycopg2.connect(
            host="localhost",
            database="scpc_indicadores",
            user="streamlit",
            password="6105/*"
        )
        return conn
    except psycopg2.Error as e:
        print(f"Erro ao conectar ao banco de dados: {e}")
        # Em uma aplicação Streamlit, você pode querer usar st.error aqui
        # st.error(f"Erro ao conectar ao banco de dados: {e}")
        return None

def create_tables_if_not_exists():
    """
    Cria as tabelas necessárias no banco de dados PostgreSQL se elas não existirem.
    """
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()

            # 1. Tabela: usuarios
            cur.execute("""
                CREATE TABLE IF NOT EXISTS usuarios (
                    username TEXT PRIMARY KEY,
                    password_hash TEXT NOT NULL,
                    tipo TEXT NOT NULL,
                    setor TEXT NOT NULL,
                    nome_completo TEXT,
                    email TEXT,
                    data_criacao TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """)
            # Inserir usuário admin padrão se a tabela estiver vazia
            cur.execute("SELECT COUNT(*) FROM usuarios;")
            if cur.fetchone()[0] == 0:
                admin_password_hash = hashlib.sha256("6105/*".encode()).hexdigest()
                cur.execute("""
                    INSERT INTO usuarios (username, password_hash, tipo, setor, nome_completo, email)
                    VALUES (%s, %s, %s, %s, %s, %s);
                """, ("admin", admin_password_hash, "Administrador", "Todos", "Administrador Padrão", "admin@example.com"))
                print("Usuário 'admin' padrão inserido.")

            # 2. Tabela: indicadores
            cur.execute("""
                CREATE TABLE IF NOT EXISTS indicadores (
                    id TEXT PRIMARY KEY,
                    nome TEXT NOT NULL UNIQUE,
                    objetivo TEXT,
                    formula TEXT,
                    variaveis JSONB,
                    unidade TEXT,
                    meta NUMERIC(10, 2),
                    comparacao TEXT,
                    tipo_grafico TEXT,
                    responsavel TEXT,
                    data_criacao TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    data_atualizacao TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # 3. Tabela: resultados
            cur.execute("""
                CREATE TABLE IF NOT EXISTS resultados (
                    indicator_id TEXT NOT NULL,
                    data_referencia TIMESTAMP WITHOUT TIME ZONE NOT NULL,
                    resultado NUMERIC(10, 2),
                    valores_variaveis JSONB,
                    observacao TEXT,
                    analise_critica JSONB,
                    data_criacao TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    data_atualizacao TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    usuario TEXT,
                    status_analise TEXT,
                    PRIMARY KEY (indicator_id, data_referencia),
                    FOREIGN KEY (indicator_id) REFERENCES indicadores(id) ON DELETE CASCADE
                );
            """)

            # 4. Tabela: configuracoes
            cur.execute("""
                CREATE TABLE IF NOT EXISTS configuracoes (
                    key TEXT PRIMARY KEY,
                    value TEXT
                );
            """)
            # Inserir configurações padrão se a tabela estiver vazia
            cur.execute("SELECT COUNT(*) FROM configuracoes;")
            if cur.fetchone()[0] == 0:
                cur.execute("INSERT INTO configuracoes (key, value) VALUES (%s, %s);", ("theme", "padrao"))
                cur.execute("INSERT INTO configuracoes (key, value) VALUES (%s, %s);", ("backup_hour", "00:00"))
                cur.execute("INSERT INTO configuracoes (key, value) VALUES (%s, %s);", ("last_backup_date", ""))
                print("Configurações padrão inseridas.")

            # 5. Tabela: log_backup
            cur.execute("""
                CREATE TABLE IF NOT EXISTS log_backup (
                    id SERIAL PRIMARY KEY,
                    timestamp TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    action TEXT,
                    file_name TEXT,
                    user_performed TEXT
                );
            """)

            # 6. Tabela: log_indicadores
            cur.execute("""
                CREATE TABLE IF NOT EXISTS log_indicadores (
                    id SERIAL PRIMARY KEY,
                    timestamp TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    action TEXT,
                    indicator_id TEXT,
                    user_performed TEXT
                );
            """)

            # 7. Tabela: log_usuarios
            cur.execute("""
                CREATE TABLE IF NOT EXISTS log_usuarios (
                    id SERIAL PRIMARY KEY,
                    timestamp TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    action TEXT,
                    username_affected TEXT,
                    user_performed TEXT
                );
            """)

            conn.commit()
            print("Tabelas verificadas/criadas com sucesso no PostgreSQL.")
            return True
        except psycopg2.Error as e:
            print(f"Erro ao criar tabelas: {e}")
            conn.rollback()
            return False
        finally:
            cur.close()
            conn.close()
    return False

# --- Funções de Persistência de Dados (DB) ---

# Usuários
def load_users():
    """
    Carrega os usuários do banco de dados PostgreSQL.
    Retorna um dicionário de usuários no formato esperado pela aplicação.
    """
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("SELECT username, password_hash, tipo, setor, nome_completo, email, data_criacao FROM usuarios;")
            users_data = cur.fetchall()
            
            users = {}
            for row in users_data:
                username, password_hash, tipo, setor, nome_completo, email, data_criacao = row
                users[username] = {
                    "password": password_hash,
                    "tipo": tipo,
                    "setor": setor,
                    "nome_completo": nome_completo if nome_completo is not None else "",
                    "email": email if email is not None else "",
                    "data_criacao": data_criacao.isoformat() if data_criacao else ""
                }
            return users
        except psycopg2.Error as e:
            print(f"Erro ao carregar usuários do banco de dados: {e}")
            return {}
        finally:
            cur.close()
            conn.close()
    return {}

def save_users(users_data):
    """
    Salva os usuários no banco de dados PostgreSQL.
    Esta função sincroniza o dicionário 'users_data' com a tabela 'usuarios'.
    Ela insere novos usuários e atualiza os existentes.
    """
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()

            cur.execute("SELECT username FROM usuarios;")
            existing_users_in_db = {row[0] for row in cur.fetchall()}

            for username, data in users_data.items():
                password_hash = data.get("password", "")
                tipo = data.get("tipo", "Visualizador")
                setor = data.get("setor", "Todos")
                nome_completo = data.get("nome_completo", "")
                email = data.get("email", "")

                if username in existing_users_in_db:
                    cur.execute("""
                        UPDATE usuarios
                        SET password_hash = %s, tipo = %s, setor = %s, nome_completo = %s, email = %s
                        WHERE username = %s;
                    """, (password_hash, tipo, setor, nome_completo, email, username))
                else:
                    cur.execute("""
                        INSERT INTO usuarios (username, password_hash, tipo, setor, nome_completo, email)
                        VALUES (%s, %s, %s, %s, %s, %s);
                    """, (username, password_hash, tipo, setor, nome_completo, email))
            
            users_to_delete = existing_users_in_db - set(users_data.keys())
            for username_to_delete in users_to_delete:
                cur.execute("DELETE FROM usuarios WHERE username = %s;", (username_to_delete,))
                print(f"Usuário '{username_to_delete}' removido do banco de dados.")

            conn.commit()
            return True
        except psycopg2.Error as e:
            print(f"Erro ao salvar usuários no banco de dados: {e}")
            conn.rollback()
            return False
        finally:
            cur.close()
            conn.close()
    return False

# Indicadores
def load_indicators():
    """
    Carrega os indicadores do banco de dados PostgreSQL.
    Retorna uma lista de dicionários de indicadores no formato esperado pela aplicação.
    """
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT id, nome, objetivo, formula, variaveis, unidade, meta, comparacao,
                       tipo_grafico, responsavel, data_criacao, data_atualizacao
                FROM indicadores;
            """)
            indicators_data = cur.fetchall()
            
            indicators = []
            for row in indicators_data:
                (id, nome, objetivo, formula, variaveis, unidade, meta, comparacao,
                 tipo_grafico, responsavel, data_criacao, data_atualizacao) = row
                
                indicators.append({
                    "id": id,
                    "nome": nome,
                    "objetivo": objetivo,
                    "formula": formula if formula is not None else "",
                    "variaveis": variaveis if variaveis is not None else {},
                    "unidade": unidade if unidade is not None else "",
                    "meta": float(meta) if meta is not None else 0.0,
                    "comparacao": comparacao if comparacao is not None else "Maior é melhor",
                    "tipo_grafico": tipo_grafico if tipo_grafico is not None else "Linha",
                    "responsavel": responsavel if responsavel is not None else "Todos",
                    "data_criacao": data_criacao.isoformat() if data_criacao else "",
                    "data_atualizacao": data_atualizacao.isoformat() if data_atualizacao else ""
                })
            return indicators
        except psycopg2.Error as e:
            print(f"Erro ao carregar indicadores do banco de dados: {e}")
            return []
        finally:
            cur.close()
            conn.close()
    return []

def save_indicators(indicators_data):
    """
    Salva os indicadores no banco de dados PostgreSQL.
    Esta função sincroniza a lista 'indicators_data' com a tabela 'indicadores'.
    Ela insere novos indicadores, atualiza os existentes e remove os que não estão mais na lista.
    """
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()

            cur.execute("SELECT id FROM indicadores;")
            existing_indicator_ids_in_db = {row[0] for row in cur.fetchall()}

            current_indicator_ids_to_save = {ind["id"] for ind in indicators_data}

            for ind in indicators_data:
                indicator_id = ind.get("id")
                nome = ind.get("nome")
                objetivo = ind.get("objetivo")
                formula = ind.get("formula")
                variaveis = Json(ind.get("variaveis", {}))
                unidade = ind.get("unidade")
                meta = ind.get("meta")
                comparacao = ind.get("comparacao")
                tipo_grafico = ind.get("tipo_grafico")
                responsavel = ind.get("responsavel")
                
                if indicator_id in existing_indicator_ids_in_db:
                    cur.execute("""
                        UPDATE indicadores
                        SET nome = %s, objetivo = %s, formula = %s, variaveis = %s,
                            unidade = %s, meta = %s, comparacao = %s, tipo_grafico = %s,
                            responsavel = %s, data_atualizacao = CURRENT_TIMESTAMP
                        WHERE id = %s;
                    """, (nome, objetivo, formula, variaveis, unidade, meta, comparacao,
                          tipo_grafico, responsavel, indicator_id))
                else:
                    if not indicator_id:
                        indicator_id = datetime.now().strftime("%Y%m%d%H%M%S%f")
                        ind["id"] = indicator_id

                    cur.execute("""
                        INSERT INTO indicadores (id, nome, objetivo, formula, variaveis,
                                                 unidade, meta, comparacao, tipo_grafico,
                                                 responsavel, data_criacao, data_atualizacao)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
                    """, (indicator_id, nome, objetivo, formula, variaveis, unidade, meta, comparacao,
                          tipo_grafico, responsavel))
            
            indicators_to_delete = existing_indicator_ids_in_db - current_indicator_ids_to_save
            for id_to_delete in indicators_to_delete:
                cur.execute("DELETE FROM indicadores WHERE id = %s;", (id_to_delete,))
                print(f"Indicador com ID '{id_to_delete}' removido do banco de dados.")

            conn.commit()
            return True
        except psycopg2.Error as e:
            print(f"Erro ao salvar indicadores no banco de dados: {e}")
            conn.rollback()
            return False
        finally:
            cur.close()
            conn.close()
    return False

# Resultados
def load_results():
    """
    Carrega os resultados dos indicadores do banco de dados PostgreSQL.
    Retorna uma lista de dicionários de resultados no formato esperado pela aplicação.
    """
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT indicator_id, data_referencia, resultado, valores_variaveis,
                       observacao, analise_critica, data_criacao, data_atualizacao,
                       usuario, status_analise
                FROM resultados;
            """)
            results_data = cur.fetchall()
            
            results = []
            for row in results_data:
                (indicator_id, data_referencia, resultado, valores_variaveis,
                 observacao, analise_critica, data_criacao, data_atualizacao,
                 usuario, status_analise) = row
                
                results.append({
                    "indicator_id": indicator_id,
                    "data_referencia": data_referencia.isoformat() if data_referencia else "",
                    "resultado": float(resultado) if resultado is not None else 0.0,
                    "valores_variaveis": valores_variaveis if valores_variaveis is not None else {},
                    "observacao": observacao if observacao is not None else "",
                    "analise_critica": analise_critica if analise_critica is not None else {}, # JSONB é carregado como dict
                    "data_criacao": data_criacao.isoformat() if data_criacao else "",
                    "data_atualizacao": data_atualizacao.isoformat() if data_atualizacao else "",
                    "usuario": usuario if usuario is not None else "System",
                    "status_analise": status_analise if status_analise is not None else "N/A"
                })
            return results
        except psycopg2.Error as e:
            print(f"Erro ao carregar resultados do banco de dados: {e}")
            return []
        finally:
            cur.close()
            conn.close()
    return []

def save_results(results_data):
    """
    Salva os resultados dos indicadores no banco de dados PostgreSQL.
    Esta função sincroniza a lista 'results_data' com a tabela 'resultados'.
    Ela insere novos resultados e atualiza os existentes.
    """
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()

            cur.execute("SELECT indicator_id, data_referencia FROM resultados;")
            existing_results_keys_in_db = {(row[0], row[1].isoformat()) for row in cur.fetchall()}

            for res in results_data:
                indicator_id = res.get("indicator_id")
                data_referencia_str = res.get("data_referencia")
                
                try:
                    data_referencia_dt = datetime.fromisoformat(data_referencia_str)
                except (ValueError, TypeError):
                    print(f"Erro: data_referencia inválida para o resultado: {data_referencia_str}")
                    continue

                resultado = res.get("resultado")
                valores_variaveis = Json(res.get("valores_variaveis", {}))
                observacao = res.get("observacao")
                
                analise_critica_data = res.get("analise_critica", {})
                # Garante que analise_critica_data é um dicionário, mesmo se vier como string JSON
                if isinstance(analise_critica_data, str):
                    try:
                        analise_critica_data = json.loads(analise_critica_data)
                    except json.JSONDecodeError:
                        analise_critica_data = {}
                analise_critica = Json(analise_critica_data)

                usuario = res.get("usuario")
                status_analise = res.get("status_analise")

                current_key = (indicator_id, data_referencia_dt.isoformat())

                if current_key in existing_results_keys_in_db:
                    cur.execute("""
                        UPDATE resultados
                        SET resultado = %s, valores_variaveis = %s, observacao = %s,
                            analise_critica = %s, data_atualizacao = CURRENT_TIMESTAMP,
                            usuario = %s, status_analise = %s
                        WHERE indicator_id = %s AND data_referencia = %s;
                    """, (resultado, valores_variaveis, observacao, analise_critica,
                          usuario, status_analise, indicator_id, data_referencia_dt))
                else:
                    cur.execute("""
                        INSERT INTO resultados (indicator_id, data_referencia, resultado,
                                                valores_variaveis, observacao, analise_critica,
                                                data_criacao, data_atualizacao, usuario, status_analise)
                        VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, %s, %s);
                    """, (indicator_id, data_referencia_dt, resultado, valores_variaveis,
                          observacao, analise_critica, usuario, status_analise))
            
            current_results_keys_to_save = {(res.get("indicator_id"), datetime.fromisoformat(res.get("data_referencia")).isoformat()) for res in results_data if res.get("data_referencia")}
            results_to_delete = existing_results_keys_in_db - current_results_keys_to_save
            for ind_id, data_ref_str in results_to_delete:
                data_ref_dt = datetime.fromisoformat(data_ref_str)
                cur.execute("DELETE FROM resultados WHERE indicator_id = %s AND data_referencia = %s;", (ind_id, data_ref_dt))
                print(f"Resultado para indicador '{ind_id}' e data '{data_ref_str}' removido do banco de dados.")

            conn.commit()
            return True
        except psycopg2.Error as e:
            print(f"Erro ao salvar resultados no banco de dados: {e}")
            conn.rollback()
            return False
        finally:
            cur.close()
            conn.close()
    return False

# Configurações
def load_config():
    """
    Carrega as configurações do banco de dados PostgreSQL.
    Retorna um dicionário de configurações.
    """
    conn = get_db_connection()
    config = {}
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("SELECT key, value FROM configuracoes;")
            config_data = cur.fetchall()
            
            for row in config_data:
                key, value = row
                config[key] = value
            
            if "theme" not in config:
                config["theme"] = "padrao"
            if "backup_hour" not in config:
                config["backup_hour"] = "00:00"
            if "last_backup_date" not in config:
                config["last_backup_date"] = ""

            return config
        except psycopg2.Error as e:
            print(f"Erro ao carregar configurações do banco de dados: {e}")
            return {"theme": "padrao", "backup_hour": "00:00", "last_backup_date": ""}
        finally:
            cur.close()
            conn.close()
    return {"theme": "padrao", "backup_hour": "00:00", "last_backup_date": ""}

def save_config(config_data):
    """
    Salva as configurações no banco de dados PostgreSQL.
    Esta função atualiza as configurações existentes e insere novas.
    """
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            
            for key, value in config_data.items():
                cur.execute("""
                    INSERT INTO configuracoes (key, value)
                    VALUES (%s, %s)
                    ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;
                """, (key, value))
            
            conn.commit()
            return True
        except psycopg2.Error as e:
            print(f"Erro ao salvar configurações no banco de dados: {e}")
            conn.rollback()
            return False
        finally:
            cur.close()
            conn.close()
    return False

# Logs de Backup
def load_backup_log():
    """
    Carrega o log de backup do banco de dados PostgreSQL.
    Retorna uma lista de dicionários de entradas de log.
    """
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("SELECT timestamp, action, file_name, user_performed FROM log_backup ORDER BY timestamp DESC;")
            log_data = cur.fetchall()
            
            log_entries = []
            for row in log_data:
                timestamp, action, file_name, user_performed = row
                log_entries.append({
                    "timestamp": timestamp.isoformat() if timestamp else "",
                    "action": action if action is not None else "",
                    "file_name": file_name if file_name is not None else "",
                    "user": user_performed if user_performed is not None else "System"
                })
            return log_entries
        except psycopg2.Error as e:
            print(f"Erro ao carregar log de backup do banco de dados: {e}")
            return []
        finally:
            cur.close()
            conn.close()
    return []

def save_backup_log(log_data):
    """
    Salva o log de backup no banco de dados PostgreSQL.
    Esta função limpa o log existente e reinseri as entradas fornecidas.
    """
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("DELETE FROM log_backup;")
            
            for entry in log_data:
                timestamp_dt = datetime.fromisoformat(entry.get("timestamp")) if entry.get("timestamp") else datetime.now()
                action = entry.get("action")
                file_name = entry.get("file_name")
                user_performed = entry.get("user", "System")
                
                cur.execute("""
                    INSERT INTO log_backup (timestamp, action, file_name, user_performed)
                    VALUES (%s, %s, %s, %s);
                """, (timestamp_dt, action, file_name, user_performed))
            
            conn.commit()
            return True
        except psycopg2.Error as e:
            print(f"Erro ao salvar o log de backup no banco de dados: {e}")
            conn.rollback()
            return False
        finally:
            cur.close()
            conn.close()
    return False

def log_backup_action(action, file_name, user_performed):
    """
    Registra uma ação de backup no log do banco de dados.
    """
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            
            log_entry_user = user_performed
            
            cur.execute("""
                INSERT INTO log_backup (action, file_name, user_performed)
                VALUES (%s, %s, %s);
            """, (action, file_name, log_entry_user))
            
            conn.commit()
            return True
        except psycopg2.Error as e:
            print(f"Erro ao registrar ação de backup no banco de dados: {e}")
            conn.rollback()
            return False
        finally:
            cur.close()
            conn.close()
    return False

# Logs de Indicadores
def load_indicator_log():
    """
    Carrega o log de indicadores do banco de dados PostgreSQL.
    Retorna uma lista de dicionários de entradas de log.
    """
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("SELECT timestamp, action, indicator_id, user_performed FROM log_indicadores ORDER BY timestamp DESC;")
            log_data = cur.fetchall()
            
            log_entries = []
            for row in log_data:
                timestamp, action, indicator_id, user_performed = row
                log_entries.append({
                    "timestamp": timestamp.isoformat() if timestamp else "",
                    "action": action if action is not None else "",
                    "indicator_id": indicator_id if indicator_id is not None else "",
                    "user": user_performed if user_performed is not None else "System"
                })
            return log_entries
        except psycopg2.Error as e:
            print(f"Erro ao carregar log de indicadores do banco de dados: {e}")
            return []
        finally:
            cur.close()
            conn.close()
    return []

def save_indicator_log(log_data):
    """
    Salva o log de indicadores no banco de dados PostgreSQL.
    Esta função limpa o log existente e reinseri as entradas fornecidas.
    """
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("DELETE FROM log_indicadores;")
            
            for entry in log_data:
                timestamp_dt = datetime.fromisoformat(entry.get("timestamp")) if entry.get("timestamp") else datetime.now()
                action = entry.get("action")
                indicator_id = entry.get("indicator_id")
                user_performed = entry.get("user", "System")
                
                cur.execute("""
                    INSERT INTO log_indicadores (timestamp, action, indicator_id, user_performed)
                    VALUES (%s, %s, %s, %s);
                """, (timestamp_dt, action, indicator_id, user_performed))
            
            conn.commit()
            return True
        except psycopg2.Error as e:
            print(f"Erro ao salvar o log de indicadores no banco de dados: {e}")
            conn.rollback()
            return False
        finally:
            cur.close()
            conn.close()
    return False

def log_indicator_action(action, indicator_id, user_performed):
    """
    Registra uma ação de indicador no log do banco de dados.
    """
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            
            log_entry_user = user_performed
            
            cur.execute("""
                INSERT INTO log_indicadores (action, indicator_id, user_performed)
                VALUES (%s, %s, %s);
            """, (action, indicator_id, log_entry_user))
            
            conn.commit()
            return True
        except psycopg2.Error as e:
            print(f"Erro ao registrar ação de indicador no banco de dados: {e}")
            conn.rollback()
            return False
        finally:
            cur.close()
            conn.close()
    return False

# Logs de Usuários
def load_user_log():
    """
    Carrega o log de usuários do banco de dados PostgreSQL.
    Retorna uma lista de dicionários de entradas de log.
    """
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("SELECT timestamp, action, username_affected, user_performed FROM log_usuarios ORDER BY timestamp DESC;")
            log_data = cur.fetchall()
            
            log_entries = []
            for row in log_data:
                timestamp, action, username_affected, user_performed = row
                log_entries.append({
                    "timestamp": timestamp.isoformat() if timestamp else "",
                    "action": action if action is not None else "",
                    "username": username_affected if username_affected is not None else "",
                    "user": user_performed if user_performed is not None else "System"
                })
            return log_entries
        except psycopg2.Error as e:
            print(f"Erro ao carregar log de usuários do banco de dados: {e}")
            return []
        finally:
            cur.close()
            conn.close()
    return []

def save_user_log(log_data):
    """
    Salva o log de usuários no banco de dados PostgreSQL.
    Esta função limpa o log existente e reinseri as entradas fornecidas.
    """
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("DELETE FROM log_usuarios;")
            
            for entry in log_data:
                timestamp_dt = datetime.fromisoformat(entry.get("timestamp")) if entry.get("timestamp") else datetime.now()
                action = entry.get("action")
                username_affected = entry.get("username")
                user_performed = entry.get("user", "System")
                
                cur.execute("""
                    INSERT INTO log_usuarios (timestamp, action, username_affected, user_performed)
                    VALUES (%s, %s, %s, %s);
                """, (timestamp_dt, action, username_affected, user_performed))
            
            conn.commit()
            return True
        except psycopg2.Error as e:
            print(f"Erro ao salvar o log de usuários no banco de dados: {e}")
            conn.rollback()
            return False
        finally:
            cur.close()
            conn.close()
    return False

def log_user_action(action, username_affected, user_performed):
    """
    Registra uma ação de usuário no log do banco de dados.
    """
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            
            log_entry_user = user_performed
            
            cur.execute("""
                INSERT INTO log_usuarios (action, username_affected, user_performed)
                VALUES (%s, %s, %s);
            """, (action, username_affected, log_entry_user))
            
            conn.commit()
            return True
        except psycopg2.Error as e:
            print(f"Erro ao registrar ação de usuário no banco de dados: {e}")
            conn.rollback()
            return False
        finally:
            cur.close()
            conn.close()
    return False

# --- Funções Auxiliares e de UI (Adaptadas para o DB) ---

SETORES = ["RH", "Financeiro", "Operações", "Marketing", "Comercial", "TI", "Logística", "Produção"]
TIPOS_GRAFICOS = ["Linha", "Barra", "Pizza", "Área", "Dispersão"]

TEMA_PADRAO = {
    "name": "Padrão",
    "primary_color": "#1E88E5",
    "secondary_color": "#26A69A",
    "background_color": "#FFFFFF",
    "text_color": "#37474F",
    "accent_color": "#FF5252",
    "chart_colors": ["#1E88E5", "#26A69A", "#FFC107", "#7E57C2", "#EC407A"],
    "is_dark": False
}

def img_to_bytes(img_path):
    try:
        img_bytes = Path(img_path).read_bytes()
        encoded = base64.b64encode(img_bytes).decode()
        return encoded
    except FileNotFoundError:
        print(f"Arquivo não encontrado: {img_path}")
        return None
    except Exception as e:
        print(f"Erro ao ler o arquivo: {e}")
        return None

def img_to_html(img_path):
    img_bytes = img_to_bytes(img_path)
    if img_bytes:
        img_html = "<img src='data:image/png;base64,{}' class='img-fluid' width='150' style='display: block; margin: 0 auto;'>".format(
            img_bytes
        )
        return img_html
    else:
        return ""

def initialize_session_state():
    """Inicializa o estado da sessão do Streamlit."""
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'current_formula_vars' not in st.session_state:
        st.session_state.current_formula_vars = []
    if 'current_var_descriptions' not in st.session_state:
        st.session_state.current_var_descriptions = {}
    if 'editing_indicator_id' not in st.session_state:
        st.session_state.editing_indicator_id = None
    if 'current_variable_values' not in st.session_state:
         st.session_state.current_variable_values = {}
    if 'should_scroll_to_top' not in st.session_state:
        st.session_state.should_scroll_to_top = False

def configure_locale():
    """Configura o locale para português do Brasil."""
    try:
        locale.setlocale(locale.LC_ALL, 'pt_BR.UTF-8')
    except locale.Error as e:
        st.warning(f"Não foi possível configurar o locale para pt_BR.UTF-8: {e}. Verifique se o locale está instalado no seu sistema.")

def scroll_to_top():
    """Define o estado para que a página role para o topo no próximo rerun."""
    st.session_state.should_scroll_to_top = True

def configure_page():
    """Configura a página do Streamlit."""
    image_path = "logo.png"
    logo_base64 = img_to_bytes(image_path)
    page_icon_value = "📈"

    if logo_base64:
        page_icon_value = f"data:image/png;base64,{logo_base64}"
    st.set_page_config(
        page_title="[DEMO]Portal de Indicadores",
        page_icon=page_icon_value,
        layout="wide"
    )

def define_menu_icons():
    """Define os ícones para o menu."""
    MENU_ICONS = {
        "Dashboard": "📈",
        "Criar Indicador": "➕",
        "Editar Indicador": "✏️",
        "Preencher Indicador": "📝",
        "Visão Geral": "📊",
        "Gerenciar Usuários": "👥",
        "Configurações": "⚙️"
    }
    return MENU_ICONS

def generate_id():
    """Gera um ID único baseado na data e hora (com microssegundos para maior unicidade)."""
    return datetime.now().strftime("%Y%m%d%H%M%S%f")

def format_date_as_month_year(date):
    """Formata a data como mês/ano."""
    try:
        return date.strftime("%b/%Y")
    except:
        try:
            return date.strftime("%m/%Y")
        except:
            return str(date)

def to_excel(df):
    """Converte um DataFrame para um arquivo Excel em memória."""
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Sheet1', index=False)
    processed_data = output.getvalue()
    return processed_data

def get_download_link(df, filename):
    """Gera um link para download de um arquivo Excel."""
    val = to_excel(df)
    b64 = base64.b64encode(val).decode()
    return f'<a href="data:application/octet-stream;base64,{b64}" download="{filename}" style="display: inline-block; padding: 0.5rem 1rem; background-color: #1E88E5; color: white; text-decoration: none; border-radius: 4px; font-weight: bold;">Baixar Excel</a>'

def create_chart(indicator_id, chart_type, TEMA_PADRAO):
    """Cria um gráfico com base no tipo especificado."""
    results = load_results()
    indicator_results = [r for r in results if r["indicator_id"] == indicator_id]

    if not indicator_results:
        return None

    df = pd.DataFrame(indicator_results)
    df["data_referencia"] = pd.to_datetime(df["data_referencia"])
    df = df.sort_values("data_referencia")
    df["data_formatada"] = df["data_referencia"].apply(format_date_as_month_year)

    indicators = load_indicators()
    indicator = next((ind for ind in indicators if ind["id"] == indicator_id), None)

    if not indicator:
        return None

    chart_colors = TEMA_PADRAO["chart_colors"]
    is_dark = TEMA_PADRAO["is_dark"]
    background_color = TEMA_PADRAO["background_color"]
    text_color = TEMA_PADRAO["text_color"]

    if chart_type == "Linha":
        fig = px.line(df, x="data_formatada", y="resultado", title=f"Evolução do Indicador: {indicator['nome']}", color_discrete_sequence=[chart_colors[0]], markers=True)
        fig.add_hline(y=float(indicator["meta"]), line_dash="dash", line_color=chart_colors[4], annotation_text="Meta")
    elif chart_type == "Barra":
        fig = px.bar(df, x="data_formatada", y="resultado", title=f"Evolução do Indicador: {indicator['nome']}", color_discrete_sequence=[chart_colors[0]])
        fig.add_hline(y=float(indicator["meta"]), line_dash="dash", line_color=chart_colors[4], annotation_text="Meta")
    elif chart_type == "Pizza":
        last_result = df.iloc[-1]["resultado"]
        fig = px.pie(names=["Resultado Atual", "Meta"], values=[last_result, float(indicator["meta"])], title=f"Último Resultado vs Meta: {indicator['nome']}", color_discrete_sequence=[chart_colors[0], chart_colors[1]], hole=0.4)
    elif chart_type == "Área":
        fig = px.area(df, x="data_formatada", y="resultado", title=f"Evolução do Indicador: {indicator['nome']}", color_discrete_sequence=[chart_colors[0]])
        fig.add_hline(y=float(indicator["meta"]), line_dash="dash", line_color=chart_colors[4], annotation_text="Meta")
    elif chart_type == "Dispersão":
        fig = px.scatter(df, x="data_formatada", y="resultado", title=f"Evolução do Indicador: {indicator['nome']}", color_discrete_sequence=[chart_colors[0]], size_max=15)
        fig.add_hline(y=float(indicator["meta"]), line_dash="dash", line_color=chart_colors[4], annotation_text="Meta")

    fig.update_layout(xaxis_title="Data de Referência", yaxis_title="Resultado", template="plotly_white")
    if is_dark:
        fig.update_layout(template="plotly_dark", paper_bgcolor=background_color, plot_bgcolor="#1E1E1E", font=dict(color=text_color))
    return fig

def show_login_page():
    """Mostra a página de login."""
    st.markdown("""
    <style>
    #MainMenu, header, footer {display: none;}
    .main { background-color: #f8f9fa; padding: 0; }
    [data-testid="stToolbar"] { display: none !important; }
    [data-testid="stAppViewContainer"] { border: none !important; }
    footer { display: none !important; }
    #MainMenu { visibility: hidden !important; }
    header { display: none !important; }
    .stTextInput > div > div > input { border-radius: 6px; border: 1px solid #E0E0E0; padding: 10px 15px; font-size: 15px; }
    div[data-testid="stForm"] button[type="submit"] { background-color: #1E88E5; color: white; border: none; border-radius: 6px; padding: 10px 15px; font-size: 16px; font-weight: 500; width: 100%; }
    .block-container { padding-top: 2rem; padding-bottom: 2rem; max-width: 600px; }
    .stAlert { border-radius: 6px; }
    .stApp { background-color: #f8f9fa; }
    </style>
    """, unsafe_allow_html=True)

    with st.container():
        image_path = "logo.png"
        if os.path.exists(image_path):
            st.markdown(f"<div style='text-align: center;'>{img_to_html(image_path)}</div>", unsafe_allow_html=True)
        else:
            st.markdown("<h1 style='text-align: center; font-size: 50px;'>📊</h1>", unsafe_allow_html=True)

        st.markdown("<h1 style='text-align: center; font-size: 30px; color: #1E88E5;'>Portal de Indicadores</h1>", unsafe_allow_html=True)
        st.markdown("<h2 style='text-align: center; font-size: 26px; color: #546E7A; margin-bottom: 20px;'>Santa Casa - Poços de Caldas</h2>", unsafe_allow_html=True)
        st.markdown("<hr style='height: 2px; background: #E0E0E0; border: none; margin: 20px 0;'>", unsafe_allow_html=True)
        st.markdown("<h3 style='font-size: 18px; color: #455A64; margin-bottom: 15px;'>Acesse sua conta</h3>", unsafe_allow_html=True)

        with st.form("login_form"):
            username = st.text_input("Nome de usuário", placeholder="Digite seu nome de usuário")
            password = st.text_input("Senha", type="password", placeholder="Digite sua senha")
            submit = st.form_submit_button("Entrar")

            if submit:
                if username and password:
                    with st.spinner("Verificando..."):
                        time.sleep(0.5)
                        if verify_credentials(username, password):
                            st.session_state.authenticated = True
                            st.session_state.username = username
                            st.success("Login realizado com sucesso!")
                            time.sleep(0.8)
                            st.rerun()
                        else:
                            st.error("Usuário ou senha incorretos.")
                else:
                    st.error("Por favor, preencha todos os campos.")
        st.markdown("<p style='text-align: center; font-size: 12px; color: #78909C; margin-top: 30px;'>© 2025 Portal de Indicadores - Santa Casa</p>", unsafe_allow_html=True)

def verify_credentials(username, password):
    """Verifica as credenciais do usuário."""
    users = load_users()
    if username in users:
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        return hashed_password == users[username].get("password", "")
    return False

def get_user_type(username):
    """Obtém o tipo de usuário."""
    users = load_users()
    if username in users:
        return users[username].get("tipo", "Visualizador")
    return "Visualizador"

def get_user_sector(username):
    """Obtém o setor do usuário."""
    users = load_users()
    if username in users:
        return users[username].get("setor", "Todos")
    return "Todos"

def create_indicator(SETORES, TIPOS_GRAFICOS):
    """Mostra a página de criação de indicador."""
    st.markdown('<div class="dashboard-card">', unsafe_allow_html=True)
    st.header("Criar Novo Indicador")
    if 'dashboard_data' in st.session_state: del st.session_state['dashboard_data']
    st.session_state.editing_indicator_id = None
    form_key = "create_indicator_form"
    if 'create_current_formula_vars' not in st.session_state: st.session_state.create_current_formula_vars = []
    if 'create_current_var_descriptions' not in st.session_state: st.session_state.create_current_var_descriptions = {}
    if 'create_sample_values' not in st.session_state: st.session_state.create_sample_values = {}
    if 'create_test_result' not in st.session_state: st.session_state.create_test_result = None
    if 'show_variable_section' not in st.session_state: st.session_state.show_variable_section = False
    if 'formula_loaded' not in st.session_state: st.session_state.formula_loaded = False

    nome = st.text_input("Nome do Indicador", key="create_nome_input", value=st.session_state.get("create_nome_input", ""))
    objetivo = st.text_area("Objetivo", key="create_objetivo_input", value=st.session_state.get("create_objetivo_input", ""))
    unidade = st.text_input("Unidade do Resultado", placeholder="Ex: %", key="create_unidade_input", value=st.session_state.get("create_unidade_input", ""))
    formula = st.text_input("Fórmula de Cálculo (Use letras para variáveis, ex: A+B/C)", placeholder="Ex: (DEMISSOES / TOTAL_FUNCIONARIOS) * 100", key="create_formula_input", value=st.session_state.get("create_formula_input", ""))
    load_formula_button = st.button("⚙️ Carregar Fórmula e Variáveis", key="load_formula_button_outside")

    if load_formula_button:
        formula_value = st.session_state.get("create_formula_input", "")
        if formula_value:
            current_detected_vars = sorted(list(set(re.findall(r'[a-zA-Z]+', formula_value))))
            st.session_state.create_current_formula_vars = current_detected_vars
            new_var_descriptions = {}
            for var in current_detected_vars: new_var_descriptions[var] = st.session_state.create_current_var_descriptions.get(var, "")
            st.session_state.create_current_var_descriptions = new_var_descriptions
            new_sample_values = {}
            for var in current_detected_vars: new_sample_values[var] = st.session_state.create_sample_values.get(var, 0.0)
            st.session_state.create_sample_values = new_sample_values
            st.session_state.create_test_result = None
            st.session_state.show_variable_section = True
            st.session_state.formula_loaded = True
            st.rerun()
        else:
            st.session_state.show_variable_section = False
            st.session_state.formula_loaded = False
            st.session_state.create_current_formula_vars = []
            st.session_state.create_current_var_descriptions = {}
            st.session_state.create_sample_values = {}
            st.session_state.create_test_result = None
            st.warning("⚠️ Por favor, insira uma fórmula para carregar.")

    st.markdown("---")
    st.subheader("Variáveis da Fórmula e Teste")
    if st.session_state.formula_loaded:
        if st.session_state.create_current_formula_vars:
            st.info(f"Variáveis detectadas na fórmula: {', '.join(st.session_state.create_current_formula_vars)}")
            st.write("Defina a descrição e insira valores de teste para cada variável:")
            with st.form(key="test_formula_form"):
                cols_desc = st.columns(min(3, len(st.session_state.create_current_formula_vars)))
                cols_sample = st.columns(min(3, len(st.session_state.create_current_formula_vars)))
                new_var_descriptions = {}
                new_sample_values = {}
                for i, var in enumerate(st.session_state.create_current_formula_vars):
                    col_idx = i % len(cols_desc)
                    with cols_desc[col_idx]:
                        new_var_descriptions[var] = st.text_input(f"Descrição para '{var}'", value=st.session_state.create_current_var_descriptions.get(var, ""), placeholder=f"Ex: {var} - Número de Atendimentos", key=f"test_desc_input_{var}")
                    col_idx = i % len(cols_sample)
                    with cols_sample[col_idx]:
                        new_sample_values[var] = st.number_input(f"Valor de Teste para '{var}'", value=float(st.session_state.create_sample_values.get(var, 0.0)), step=0.01, format="%.2f", key=f"test_sample_input_{var}")
                st.session_state.create_current_var_descriptions = new_var_descriptions
                st.session_state.create_sample_values = new_sample_values
                test_formula_button = st.form_submit_button("✨ Testar Fórmula")
                if test_formula_button:
                     formula_str = st.session_state.get("create_formula_input", "")
                     variable_values = st.session_state.create_sample_values
                     unidade_value = st.session_state.get("create_unidade_input", "")
                     if not formula_str: st.warning("⚠️ Por favor, insira uma fórmula para testar."); st.session_state.create_test_result = None
                     elif not variable_values and formula_str:
                          try: calculated_result = float(sympify(formula_str)); st.session_state.create_test_result = calculated_result
                          except (SympifyError, ValueError) as e: st.error(f"❌ Erro ao calcular a fórmula: Verifique a sintaxe. Detalhes: {e}"); st.session_state.create_test_result = None
                          except Exception as e: st.error(f"❌ Erro inesperado ao calcular a fórmula: {e}"); st.session_state.create_test_result = None
                     elif variable_values:
                          try:
                              var_symbols = symbols(list(variable_values.keys())); expr = sympify(formula_str, locals=dict(zip(variable_values.keys(), var_symbols)))
                              subs_dict = {symbols(var): float(value) for var, value in variable_values.items()}; calculated_result = float(expr.subs(subs_dict))
                              st.session_state.create_test_result = calculated_result
                          except SympifyError as e: st.error(f"❌ Erro ao calcular a fórmula: Verifique a sintaxe. Detalhes: {e}"); st.session_state.create_test_result = None
                          except ZeroDivisionError: st.error("❌ Erro ao calcular a fórmula: Divisão por zero com os valores de teste fornecidos."); st.session_state.create_test_result = None
                          except Exception as e:
                               if "cannot create 'dict_keys' instances" in str(e): st.error("❌ Erro interno ao processar as variáveis da fórmula. Verifique se as variáveis na fórmula correspondem às variáveis definidas para o indicador.")
                               else: st.error(f"❌ Erro inesperado ao calcular a fórmula: {e}"); st.session_state.create_test_result = None
                if st.session_state.create_test_result is not None:
                     unidade_value = st.session_state.get("create_unidade_input", "")
                     st.markdown(f"**Resultado do Teste:** **{st.session_state.create_test_result:.2f}{unidade_value}**")
        else:
             st.warning("Nenhuma variável (letras) encontrada na fórmula. O resultado será um valor fixo.")
             st.session_state.create_current_formula_vars = []
             st.session_state.create_current_var_descriptions = {}
             st.session_state.create_sample_values = {}
             st.session_state.create_test_result = None
    else:
        st.info("Insira a fórmula acima e clique em '⚙️ Carregar Fórmula e Variáveis' para definir as variáveis e testar.")
        st.session_state.create_current_formula_vars = []
        st.session_state.create_current_var_descriptions = {}
        st.session_state.create_sample_values = {}
        st.session_state.create_test_result = None
        st.session_state.show_variable_section = False
        st.session_state.formula_loaded = False

    st.markdown("---")
    with st.form(key=form_key):
        meta = st.number_input("Meta", step=0.01, format="%.2f", key=f"{form_key}_meta", value=st.session_state.get(f"{form_key}_meta", 0.0))
        comparacao = st.selectbox("Comparação", ["Maior é melhor", "Menor é melhor"], key=f"{form_key}_comparacao", index=["Maior é melhor", "Menor é melhor"].index(st.session_state.get(f"{form_key}_comparacao", "Maior é melhor")))
        tipo_grafico = st.selectbox("Tipo de Gráfico Padrão", TIPOS_GRAFICOS, key=f"{form_key}_tipo_grafico", index=TIPOS_GRAFICOS.index(st.session_state.get(f"{form_key}_tipo_grafico", TIPOS_GRAFICOS[0])) if TIPOS_GRAFICOS else 0)
        responsavel = st.selectbox("Setor Responsável", SETORES, key=f"{form_key}_responsavel", index=SETORES.index(st.session_state.get(f"{form_key}_responsavel", SETORES[0])) if SETORES else 0)
        create_button = st.form_submit_button("➕ Criar")

    if create_button:
        nome_submitted = st.session_state.get("create_nome_input", "")
        objetivo_submitted = st.session_state.get("create_objetivo_input", "")
        formula_submitted = st.session_state.get("create_formula_input", "")
        unidade_submitted = st.session_state.get("create_unidade_input", "")
        meta_submitted = st.session_state.get(f"{form_key}_meta", 0.0)
        comparacao_submitted = st.session_state.get(f"{form_key}_comparacao", "Maior é melhor")
        tipo_grafico_submitted = st.session_state.get(f"{form_key}_tipo_grafico", TIPOS_GRAFICOS[0] if TIPOS_GRAFICOS else "")
        responsavel_submitted = st.session_state.get(f"{form_key}_responsavel", SETORES[0] if SETORES else "")
        variaveis_desc_submitted = st.session_state.create_current_var_descriptions

        if not nome_submitted or not objetivo_submitted or not formula_submitted:
             st.warning("⚠️ Por favor, preencha todos os campos obrigatórios (Nome, Objetivo, Fórmula).")
        else:
            if formula_submitted:
                try:
                    var_symbols = symbols(st.session_state.create_current_formula_vars)
                    sympify(formula_submitted, locals=dict(zip(st.session_state.create_current_formula_vars, var_symbols)))
                except (SympifyError, ValueError, TypeError) as e: st.error(f"❌ Erro na sintaxe da fórmula: {e}"); return
                except Exception as e: st.error(f"❌ Erro inesperado ao validar a fórmula: {e}"); return

            with st.spinner("Criando indicador..."):
                time.sleep(0.5)
                indicators = load_indicators()
                if any(ind["nome"] == nome_submitted for ind in indicators):
                    st.error(f"❌ Já existe um indicador com o nome '{nome_submitted}'.")
                else:
                    new_indicator = {
                        "id": generate_id(),
                        "nome": nome_submitted,
                        "objetivo": objetivo_submitted,
                        "formula": formula_submitted,
                        "variaveis": variaveis_desc_submitted,
                        "unidade": unidade_submitted,
                        "meta": meta_submitted,
                        "comparacao": comparacao_submitted,
                        "tipo_grafico": tipo_grafico_submitted,
                        "responsavel": responsavel_submitted,
                        "data_criacao": datetime.now().isoformat(),
                        "data_atualizacao": datetime.now().isoformat()
                    }
                    indicators.append(new_indicator)
                    save_indicators(indicators)
                    log_indicator_action("Indicador criado", new_indicator["id"], st.session_state.username)
                    st.success(f"✅ Indicador '{nome_submitted}' criado com sucesso!")
                    time.sleep(2)
                    if "create_nome_input" in st.session_state: del st.session_state["create_nome_input"]
                    if "create_objetivo_input" in st.session_state: del st.session_state["create_objetivo_input"]
                    if "create_unidade_input" in st.session_state: del st.session_state["create_unidade_input"]
                    if "create_formula_input" in st.session_state: del st.session_state["create_formula_input"]
                    if form_key in st.session_state: del st.session_state[form_key]
                    st.session_state.create_current_formula_vars = []
                    st.session_state.create_current_var_descriptions = {}
                    st.session_state.create_sample_values = {}
                    st.session_state.create_test_result = None
                    st.session_state.show_variable_section = False
                    st.session_state.formula_loaded = False
                    scroll_to_top()
                    st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

def edit_indicator(SETORES, TIPOS_GRAFICOS):
    """Mostra a página de edição de indicador com fórmula dinâmica."""
    st.markdown('<div class="dashboard-card">', unsafe_allow_html=True)
    st.header("Editar Indicador")
    st.session_state["indicators"] = load_indicators()
    indicators = st.session_state["indicators"]

    if not indicators:
        st.info("Nenhum indicador cadastrado. Utilize a opção 'Criar Indicador' para começar.")
        st.markdown('</div>', unsafe_allow_html=True)
        return

    indicator_names = [ind["nome"] for ind in indicators]
    selected_indicator_id_from_state = st.session_state.editing_indicator_id
    initial_index = 0
    if selected_indicator_id_from_state:
         try: initial_index = next(i for i, ind in enumerate(indicators) if ind["id"] == selected_indicator_id_from_state)
         except StopIteration:
             st.session_state.editing_indicator_id = None
             st.session_state.current_formula_vars = []
             st.session_state.current_var_descriptions = {}
             st.session_state.current_variable_values = {}

    selected_indicator_name = st.selectbox("Selecione um indicador para editar:", indicator_names, index=initial_index if initial_index < len(indicator_names) else 0, key="edit_indicator_select")
    selected_indicator = next((ind for ind in indicators if ind["nome"] == selected_indicator_name), None)

    if selected_indicator:
        if st.session_state.editing_indicator_id != selected_indicator["id"] or not st.session_state.current_formula_vars:
             st.session_state.editing_indicator_id = selected_indicator["id"]
             existing_formula = selected_indicator.get("formula", "")
             st.session_state.current_formula_vars = sorted(list(set(re.findall(r'[a-zA-Z]+', existing_formula))))
             st.session_state.current_var_descriptions = selected_indicator.get("variaveis", {})
             for var in st.session_state.current_formula_vars:
                  if var not in st.session_state.current_var_descriptions: st.session_state.current_var_descriptions[var] = ""
             vars_to_remove = [v for v in st.session_state.current_var_descriptions if v not in st.session_state.current_formula_vars]
             for var in vars_to_remove: del st.session_state.current_var_descriptions[var]
             st.session_state.current_variable_values = {}

        delete_state_key = f"delete_state_{selected_indicator['id']}"
        if delete_state_key not in st.session_state: st.session_state[delete_state_key] = None

        with st.form(key=f"edit_form_{selected_indicator['id']}"):
            nome = st.text_input("Nome do Indicador", value=selected_indicator["nome"])
            objetivo = st.text_area("Objetivo", value=selected_indicator["objetivo"])
            unidade = st.text_input("Unidade do Resultado", value=selected_indicator.get("unidade", ""), placeholder="Ex: %", key=f"edit_unidade_input_{selected_indicator['id']}")
            formula = st.text_input("Fórmula de Cálculo (Use letras para variáveis, ex: A+B/C)", value=selected_indicator.get("formula", ""), placeholder="Ex: (DEMISSOES / TOTAL_FUNCIONARIOS) * 100", key=f"edit_formula_input_{selected_indicator['id']}")
            current_detected_vars = sorted(list(set(re.findall(r'[a-zA-Z]+', formula))))
            if st.session_state.current_formula_vars != current_detected_vars:
                 st.session_state.current_formula_vars = current_detected_vars
                 new_var_descriptions = {}
                 for var in current_detected_vars: new_var_descriptions[var] = st.session_state.current_var_descriptions.get(var, "")
                 st.session_state.current_var_descriptions = new_var_descriptions

            st.markdown("---")
            st.subheader("Definição das Variáveis na Fórmula")
            if st.session_state.current_formula_vars:
                st.info(f"Variáveis detectadas na fórmula: {', '.join(st.session_state.current_formula_vars)}")
                st.write("Defina a descrição para cada variável:")
                cols = st.columns(min(3, len(st.session_state.current_formula_vars)))
                new_var_descriptions = {}
                for i, var in enumerate(st.session_state.current_formula_vars):
                    col_idx = i % len(cols)
                    with cols[col_idx]:
                        new_var_descriptions[var] = st.text_input(
                            f"Descrição para '{var}'",
                            value=st.session_state.current_var_descriptions.get(var, ""),
                            placeholder=f"Ex: {var} - Número de Atendimentos",
                            key=f"desc_input_{var}_edit_{selected_indicator['id']}"
                        )
                st.session_state.current_var_descriptions = new_var_descriptions
            else:
                st.warning("Nenhuma variável (letras) encontrada na fórmula. O resultado será um valor fixo.")
                st.session_state.current_var_descriptions = {}

            st.markdown("---")
            meta = st.number_input("Meta", value=float(selected_indicator.get("meta", 0.0)), step=0.01, format="%.2f")
            comparacao = st.selectbox("Comparação", ["Maior é melhor", "Menor é melhor"], index=0 if selected_indicator.get("comparacao", "Maior é melhor") == "Maior é melhor" else 1)
            tipo_grafico = st.selectbox("Tipo de Gráfico Padrão", TIPOS_GRAFICOS, index=TIPOS_GRAFICOS.index(selected_indicator.get("tipo_grafico", "Linha")) if selected_indicator.get("tipo_grafico", "Linha") in TIPOS_GRAFICOS else 0)
            responsavel = st.selectbox("Setor Responsável", SETORES, index=SETORES.index(selected_indicator.get("responsavel", SETORES[0])) if selected_indicator.get("responsavel", SETORES[0]) in SETORES else 0)

            col1, col2, col3 = st.columns([1, 3, 1])
            st.markdown("""<style>[data-testid="stForm"] div:nth-child(3) > div:first-child { text-align: right; }</style>""", unsafe_allow_html=True)
            with col1: submit = st.form_submit_button("💾 Salvar")
            with col3: delete_button_clicked = st.form_submit_button("️ Excluir", type="secondary")

            if submit:
                if formula:
                    try:
                        var_symbols = symbols(st.session_state.current_formula_vars)
                        sympify(formula, locals=dict(zip(st.session_state.current_formula_vars, var_symbols)))
                    except SympifyError as e: st.error(f"❌ Erro na sintaxe da fórmula: {e}"); return
                    except Exception as e: st.error(f"❌ Erro inesperado ao validar a fórmula: {e}"); return

                if nome and objetivo and formula:
                    if nome != selected_indicator["nome"] and any(ind["nome"] == nome for ind in indicators if ind["id"] != selected_indicator["id"]):
                        st.error(f"❌ Já existe um indicador com o nome '{nome}'.")
                    else:
                        for ind in indicators:
                            if ind["id"] == selected_indicator["id"]:
                                ind["nome"] = nome; ind["objetivo"] = objetivo; ind["formula"] = formula
                                ind["variaveis"] = st.session_state.current_var_descriptions; ind["unidade"] = unidade
                                ind["meta"] = meta; ind["comparacao"] = comparacao; ind["tipo_grafico"] = tipo_grafico
                                ind["responsavel"] = responsavel; ind["data_atualizacao"] = datetime.now().isoformat()
                        save_indicators(indicators)
                        st.session_state["indicators"] = load_indicators()
                        with st.spinner("Atualizando indicador..."):
                            st.success(f"✅ Indicador '{nome}' atualizado com sucesso!")
                            time.sleep(2)
                        st.session_state.editing_indicator_id = None
                        st.session_state.current_formula_vars = []
                        st.session_state.current_var_descriptions = {}
                        st.session_state.current_variable_values = {}
                        scroll_to_top()
                        st.rerun()
                else:
                    st.warning("⚠️ Por favor, preencha todos os campos obrigatórios (Nome, Objetivo, Fórmula).")

            if delete_button_clicked:
                 st.session_state[delete_state_key] = 'confirming'
                 st.rerun()

        if st.session_state.get(delete_state_key) == 'confirming':
            st.warning(f"Tem certeza que deseja excluir o indicador '{selected_indicator['nome']}'?")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ Sim, Excluir", key=f"confirm_delete_{selected_indicator['id']}"):
                    st.session_state[delete_state_key] = 'deleting'
                    st.rerun()
            with col2:
                if st.button("❌ Cancelar", key=f"cancel_delete_{selected_indicator['id']}"):
                    st.info("Exclusão cancelada.")
                    st.session_state[delete_state_key] = None
                    st.rerun()

        if st.session_state.get(delete_state_key) == 'deleting':
            delete_indicator(selected_indicator["id"], st.session_state.username)
            with st.spinner("Excluindo indicador..."):
                st.success(f"Indicador '{selected_indicator['nome']}' excluído com sucesso!")
                time.sleep(2)
            st.session_state[delete_state_key] = None
            st.session_state.editing_indicator_id = None
            st.session_state.current_formula_vars = []
            st.session_state.current_var_descriptions = {}
            st.session_state.current_variable_values = {}
            scroll_to_top()
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

def delete_indicator(indicator_id, user_performed):
    """Exclui um indicador e seus resultados associados do banco de dados."""
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("DELETE FROM indicadores WHERE id = %s;", (indicator_id,))
            conn.commit()
            log_indicator_action("Indicador excluído", indicator_id, user_performed)
            return True
        except psycopg2.Error as e:
            print(f"Erro ao excluir indicador do banco de dados: {e}")
            conn.rollback()
            return False
        finally:
            cur.close()
            conn.close()
    return False

def display_result_with_delete(result, selected_indicator):
    """Exibe um resultado com a opção de excluir e ícone de status da meta."""
    data_referencia = result.get('data_referencia')
    if data_referencia:
        col1, col2, col3, col4, col5, col6 = st.columns([2, 2, 2, 2, 2, 1])
        with col1: st.write(pd.to_datetime(data_referencia).strftime("%B/%Y"))
        with col2:
            resultado = result.get('resultado', 'N/A'); unidade = selected_indicator.get('unidade', ''); meta = selected_indicator.get('meta', None); comparacao = selected_indicator.get('comparacao', 'Maior é melhor')
            icone = ":white_circle:"
            try:
                resultado_float = float(resultado); meta_float = float(meta)
                if comparacao == "Maior é melhor": icone = ":white_check_mark:" if resultado_float >= meta_float else ":x:"
                elif comparacao == "Menor é melhor": icone = ":white_check_mark:" if resultado_float <= meta_float else ":x:"
            except (TypeError, ValueError): pass
            st.markdown(f"{icone} **{resultado:.2f}{unidade}**")
        with col3: st.write(result.get('observacao', 'N/A'))
        with col4: st.write(result.get('status_analise', 'N/A'))
        with col5: st.write(pd.to_datetime(result.get('data_atualizacao')).strftime("%d/%m/%Y %H:%M") if result.get('data_atualizacao') else 'N/A')
        with col6:
            if st.button("🗑️", key=f"delete_result_{result.get('data_referencia')}"):
                delete_result(selected_indicator['id'], data_referencia, st.session_state.username)
    else:
        st.warning("Data de referência ausente. Impossível excluir este resultado.")

def fill_indicator(SETORES, TEMA_PADRAO):
    """Mostra a página de preenchimento de indicador com calculadora dinâmica."""
    st.markdown('<div class="dashboard-card">', unsafe_allow_html=True)
    st.header("Preencher Indicador")
    indicators = load_indicators()

    if not indicators:
        st.info("Nenhum indicador cadastrado. Utilize a opção 'Criar Indicador' para começar.")
        st.markdown('</div>', unsafe_allow_html=True)
        return

    user_type = st.session_state.user_type
    user_sector = st.session_state.user_sector
    user_name = st.session_state.get("username", "Usuário não identificado")

    if user_type == "Operador":
        indicators = [ind for ind in indicators if ind["responsavel"] == user_sector]
        if not indicators:
            st.info(f"Não há indicadores associados ao seu setor ({user_sector}).")
            st.markdown('</div>', unsafe_allow_html=True)
            return

    indicator_names = [ind["nome"] for ind in indicators]
    selected_indicator_name = st.selectbox("Selecione um indicador para preencher:", indicator_names)
    selected_indicator = next((ind for ind in indicators if ind["nome"] == selected_indicator_name), None)

    if selected_indicator:
        st.subheader(f"Informações do Indicador: {selected_indicator['nome']}")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**Objetivo:** {selected_indicator['objetivo']}")
            if selected_indicator.get("formula"): 
                st.markdown(f"**Fórmula de Cálculo:** `{selected_indicator['formula']}`")
            else: 
                st.markdown(f"**Fórmula de Cálculo:** Não definida (preenchimento direto)")
            st.markdown(f"**Unidade do Resultado:** {selected_indicator.get('unidade', 'Não definida')}")
        with col2:
            meta_display = f"{float(selected_indicator.get('meta', 0.0)):.2f}{selected_indicator.get('unidade', '')}"
            st.markdown(f"**Meta:** {meta_display}")
            st.markdown(f"**Comparação:** {selected_indicator['comparacao']}")
            st.markdown(f"**Setor Responsável:** {selected_indicator['responsavel']}")

        if selected_indicator.get("variaveis"):
            st.markdown("---")
            st.subheader("Variáveis do Indicador")
            vars_list = list(selected_indicator["variaveis"].items())
            if vars_list:
                cols = st.columns(min(3, len(vars_list)))
                for i, (var, desc) in enumerate(vars_list):
                    col_idx = i % len(cols)
                    with cols[col_idx]:
                        st.markdown(f"**{var}:** {desc or 'Sem descrição'}")
        st.markdown("---")

        results = load_results()
        indicator_results = [r for r in results if r["indicator_id"] == selected_indicator["id"]]

        filled_periods = set()
        for result in indicator_results:
            if "data_referencia" in result:
                try:
                    date_ref = pd.to_datetime(result["data_referencia"]).to_period('M')
                    filled_periods.add(date_ref)
                except: 
                    pass

        current_date = datetime.now()
        available_periods = []
        for year in range(current_date.year - 5, current_date.year + 1):
            for month in range(1, 13):
                period = pd.Period(year=year, month=month, freq='M')
                if period > pd.Period(current_date, freq='M'): 
                    continue
                if period not in filled_periods: 
                    available_periods.append(period)

        if not available_periods:
            st.info("Todos os períodos relevantes já foram preenchidos para este indicador.")
        else:
            st.subheader("Adicionar Novo Resultado")
            with st.form("adicionar_resultado"):
                available_periods.sort(reverse=True)
                period_options = [f"{p.strftime('%B/%Y')}" for p in available_periods]
                selected_period_str = st.selectbox("Selecione o período para preenchimento:", period_options)
                selected_period = next((p for p in available_periods if p.strftime('%B/%Y') == selected_period_str), None)
                selected_month, selected_year = selected_period.month, selected_period.year if selected_period else (None, None)

                calculated_result = None
                if selected_indicator.get("formula") and selected_indicator.get("variaveis"):
                    st.markdown("#### Valores das Variáveis")
                    st.info(f"Insira os valores para calcular o resultado usando a fórmula: `{selected_indicator['formula']}`")
                    vars_to_fill = list(selected_indicator["variaveis"].items())
                    if vars_to_fill:
                        variable_values_key = f"variable_values_form_{selected_indicator['id']}_{selected_period_str}"
                        if variable_values_key not in st.session_state: 
                            st.session_state[variable_values_key] = {}
                        cols = st.columns(min(3, len(vars_to_fill)))
                        for i, (var, desc) in enumerate(vars_to_fill):
                            col_idx = i % len(cols)
                            with cols[col_idx]:
                                default_value = st.session_state[variable_values_key].get(var, 0.0)
                                st.session_state[variable_values_key][var] = st.number_input(
                                    f"{var} ({desc or 'Sem descrição'})", 
                                    value=float(default_value), 
                                    step=0.01, 
                                    format="%.2f", 
                                    key=f"var_input_{var}_{selected_indicator['id']}_{selected_period_str}"
                                )
                        test_button_clicked = st.form_submit_button("✨ Calcular Resultado")
                        calculated_result_state_key = f"calculated_result_{selected_indicator['id']}_{selected_period_str}"
                        if st.session_state.get(calculated_result_state_key) is not None:
                            calculated_result = st.session_state[calculated_result_state_key]
                            result_display = f"{calculated_result:.2f}{selected_indicator.get('unidade', '')}"
                            st.markdown(f"**Resultado Calculado:** **{result_display}**")
                            meta_valor = float(selected_indicator.get('meta', 0.0))
                            comparacao_tipo = selected_indicator['comparacao']
                            if comparacao_tipo == "Maior é melhor":
                                if calculated_result >= meta_valor: 
                                    st.success(f"🎉 Meta Atingida! O resultado ({result_display}) é maior ou igual à meta ({meta_valor:.2f}{selected_indicator.get('unidade', '')}).")
                                else: 
                                    st.warning(f"⚠️ Meta Não Atingida. O resultado ({result_display}) é menor que a meta ({meta_valor:.2f}{selected_indicator.get('unidade', '')}).")
                            elif comparacao_tipo == "Menor é melhor":
                                if calculated_result <= meta_valor: 
                                    st.success(f"🎉 Meta Atingida! O resultado ({result_display}) é menor ou igual à meta ({meta_valor:.2f}{selected_indicator.get('unidade', '')}).")
                                else: 
                                    st.warning(f"⚠️ Meta Não Atingida. O resultado ({result_display}) é maior que a meta ({meta_valor:.2f}{selected_indicator.get('unidade', '')}).")
                    else:
                        st.warning("O indicador tem uma fórmula, mas nenhuma variável definida. O resultado será um valor fixo.")
                        resultado_input_value = st.number_input(
                            "Resultado", 
                            step=0.01, 
                            format="%.2f", 
                            key=f"direct_result_input_{selected_indicator['id']}_{selected_period_str}"
                        )
                        variable_values_key = f"variable_values_form_{selected_indicator['id']}_{selected_period_str}"
                        st.session_state[variable_values_key] = {}
                        calculated_result_state_key = f"calculated_result_{selected_indicator['id']}_{selected_period_str}"
                        st.session_state[calculated_result_state_key] = None
                else:
                    resultado_input_value = st.number_input(
                        "Resultado", 
                        step=0.01, 
                        format="%.2f", 
                        key=f"direct_result_input_{selected_indicator['id']}_{selected_period_str}"
                    )
                    variable_values_key = f"variable_values_form_{selected_indicator['id']}_{selected_period_str}"
                    st.session_state[variable_values_key] = {}
                    calculated_result_state_key = f"calculated_result_{selected_indicator['id']}_{selected_period_str}"
                    st.session_state[calculated_result_state_key] = None

                observacoes = st.text_area(
                    "Observações (opcional)", 
                    placeholder="Adicione informações relevantes sobre este resultado", 
                    key=f"obs_input_{selected_indicator['id']}_{selected_period_str}"
                )
                st.markdown("### Análise Crítica (5W2H)")
                st.markdown("""<div style="background-color: #f8f9fa; padding: 10px; border-radius: 5px; margin-bottom: 15px;"><p style="margin: 0; font-size: 14px;">A metodologia 5W2H ajuda a estruturar a análise crítica de forma completa, abordando todos os aspectos relevantes da situação.</p></div>""", unsafe_allow_html=True)
                what = st.text_area(
                    "O que (What)", 
                    placeholder="O que está acontecendo? Qual é a situação atual do indicador?", 
                    key=f"what_input_{selected_indicator['id']}_{selected_period_str}"
                )
                why = st.text_area(
                    "Por que (Why)", 
                    placeholder="Por que isso está acontecendo? Quais são as causas?", 
                    key=f"why_input_{selected_indicator['id']}_{selected_period_str}"
                )
                who = st.text_area(
                    "Quem (Who)", 
                    placeholder="Quem é responsável? Quem está envolvido?", 
                    key=f"who_input_{selected_indicator['id']}_{selected_period_str}"
                )
                when = st.text_area(
                    "Quando (When)", 
                    placeholder="Quando isso aconteceu? Qual é o prazo para resolução?", 
                    key=f"when_input_{selected_indicator['id']}_{selected_period_str}"
                )
                where = st.text_area(
                    "Onde (Where)", 
                    placeholder="Onde ocorre a situação? Em qual processo ou área?", 
                    key=f"where_input_{selected_indicator['id']}_{selected_period_str}"
                )
                how = st.text_area(
                    "Como (How)", 
                    placeholder="Como resolver a situação? Quais ações devem ser tomadas?", 
                    key=f"how_input_{selected_indicator['id']}_{selected_period_str}"
                )
                howMuch = st.text_area(
                    "Quanto custa (How Much)", 
                    placeholder="Quanto custará implementar a solução? Quais recursos são necessários?", 
                    key=f"howmuch_input_{selected_indicator['id']}_{selected_period_str}"
                )
                submitted = st.form_submit_button("✔️ Salvar")

            if test_button_clicked:
                formula_str = selected_indicator.get("formula", "")
                variable_values = st.session_state.get(variable_values_key, {})
                if not formula_str: 
                    st.warning("⚠️ Este indicador não possui fórmula definida para calcular.")
                    st.session_state[calculated_result_state_key] = None
                elif not variable_values and formula_str:
                    try: 
                        calculated_result = float(sympify(formula_str))
                        st.session_state[calculated_result_state_key] = calculated_result
                    except (SympifyError, ValueError) as e: 
                        st.error(f"❌ Erro ao calcular a fórmula: Verifique a sintaxe ou se todas as variáveis foram inseridas. Detalhes: {e}")
                        st.session_state[calculated_result_state_key] = None
                    except Exception as e: 
                        st.error(f"❌ Erro inesperado ao calcular a fórmula: {e}")
                        st.session_state[calculated_result_state_key] = None
                elif variable_values:
                    try:
                        var_symbols = symbols(list(variable_values.keys()))
                        expr = sympify(formula_str, locals=dict(zip(variable_values.keys(), var_symbols)))
                        subs_dict = {symbols(var): float(value) for var, value in variable_values.items()}
                        calculated_result = float(expr.subs(subs_dict))
                        st.session_state[calculated_result_state_key] = calculated_result
                    except SympifyError as e: 
                        st.error(f"❌ Erro ao calcular a fórmula: Verifique a sintaxe. Detalhes: {e}")
                        st.session_state[calculated_result_state_key] = None
                    except ZeroDivisionError: 
                        st.error("❌ Erro ao calcular a fórmula: Divisão por zero com os valores de teste fornecidos.")
                        st.session_state[calculated_result_state_key] = None
                    except Exception as e:
                        if "cannot create 'dict_keys' instances" in str(e): 
                            st.error("❌ Erro interno ao processar as variáveis da fórmula. Verifique se as variáveis na fórmula correspondem às variáveis definidas para o indicador.")
                        else: 
                            st.error(f"❌ Erro inesperado ao calcular a fórmula: {e}")
                        st.session_state[calculated_result_state_key] = None
                st.rerun()
            elif submitted:
                final_result_to_save = None
                values_to_save = {}
                if selected_indicator.get("formula") and selected_indicator.get("variaveis"):
                    final_result_to_save = st.session_state.get(calculated_result_state_key)
                    values_to_save = st.session_state.get(variable_values_key, {})
                    if final_result_to_save is None: 
                        st.warning("⚠️ Por favor, calcule o resultado antes de salvar.")
                        return
                else:
                    final_result_to_save = resultado_input_value
                    values_to_save = {}

                if final_result_to_save is not None:
                    data_referencia_iso = datetime(selected_year, selected_month, 1).isoformat()
                    analise_critica = {
                        "what": what, 
                        "why": why, 
                        "who": who, 
                        "when": when, 
                        "where": where, 
                        "how": how, 
                        "howMuch": howMuch
                    }
                    campos_preenchidos = sum(1 for campo in analise_critica.values() if campo and campo.strip())
                    total_campos = 7
                    if campos_preenchidos == 0: 
                        status_analise = "❌ Não preenchida"
                    elif campos_preenchidos == total_campos: 
                        status_analise = "✅ Preenchida completamente"
                    else: 
                        status_analise = f"⚠️ Preenchida parcialmente ({campos_preenchidos}/{total_campos})"
                    analise_critica["status_preenchimento"] = status_analise
                    
                    new_result = {
                        "indicator_id": selected_indicator["id"],
                        "data_referencia": data_referencia_iso,
                        "resultado": final_result_to_save,
                        "valores_variaveis": values_to_save,
                        "observacao": observacoes,
                        "analise_critica": analise_critica,
                        "data_criacao": datetime.now().isoformat(),
                        "data_atualizacao": datetime.now().isoformat(),
                        "usuario": user_name,
                        "status_analise": status_analise
                    }
                    
                    all_results = load_results()
                    all_results = [r for r in all_results if not (r["indicator_id"] == new_result["indicator_id"] and r["data_referencia"] == new_result["data_referencia"])]
                    all_results.append(new_result)
                    save_results(all_results)

                    with st.spinner("Salvando resultado..."):
                        st.success(f"✅ Resultado adicionado com sucesso para {datetime(selected_year, selected_month, 1).strftime('%B/%Y')}!")
                        time.sleep(2)
                    if variable_values_key in st.session_state: 
                        del st.session_state[variable_values_key]
                    if calculated_result_state_key in st.session_state: 
                        del st.session_state[calculated_result_state_key]
                    scroll_to_top()
                    st.rerun()
                else:
                    st.warning("⚠️ Por favor, informe o resultado ou calcule-o antes de salvar.")

        st.subheader("Resultados Anteriores")
        if indicator_results:
            indicator_results_sorted = sorted(indicator_results, key=lambda x: x.get("data_referencia", ""), reverse=True)
            unidade_display = selected_indicator.get('unidade', '')
            if selected_indicator.get("formula") and selected_indicator.get("variaveis"):
                cols_header = st.columns([1.5] + [1] * len(selected_indicator["variaveis"]) + [1, 2, 2, 1])
                with cols_header[0]: 
                    st.markdown("**Período**")
                for i, var in enumerate(selected_indicator["variaveis"].keys()):
                    with cols_header[i+1]:
                        st.markdown(f"**{var}**")
                with cols_header[len(selected_indicator["variaveis"])+1]: 
                    st.markdown(f"**Resultado ({unidade_display})**")
                with cols_header[len(selected_indicator["variaveis"])+2]: 
                    st.markdown("**Observações**")
                with cols_header[len(selected_indicator["variaveis"])+3]: 
                    st.markdown("**Análise Crítica**")
                with cols_header[len(selected_indicator["variaveis"])+4]: 
                    st.markdown("**Ações**")
                
                for result in indicator_results_sorted:
                    cols_data = st.columns([1.5] + [1] * len(selected_indicator["variaveis"]) + [1, 2, 2, 1])
                    data_referencia = result.get('data_referencia')
                    if data_referencia:
                        with cols_data[0]: 
                            st.write(pd.to_datetime(data_referencia).strftime("%B/%Y"))
                        valores_vars = result.get("valores_variaveis", {})
                        for i, var in enumerate(selected_indicator["variaveis"].keys()):
                            with cols_data[i+1]:
                                var_value = valores_vars.get(var)
                                if isinstance(var_value, (int, float)): 
                                    st.write(f"{var_value:.2f}")
                                else: 
                                    st.write('N/A')
                        with cols_data[len(selected_indicator["variaveis"])+1]:
                            result_value = result.get('resultado')
                            unidade = selected_indicator.get('unidade', '')
                            meta = selected_indicator.get('meta', None)
                            comparacao = selected_indicator.get('comparacao', 'Maior é melhor')
                            icone = ":white_circle:"
                            try:
                                resultado_float = float(result_value)
                                meta_float = float(meta)
                                if comparacao == "Maior é melhor": 
                                    icone = ":white_check_mark:" if resultado_float >= meta_float else ":x:"
                                elif comparacao == "Menor é melhor": 
                                    icone = ":white_check_mark:" if resultado_float <= meta_float else ":x:"
                            except (TypeError, ValueError): 
                                pass
                            if isinstance(result_value, (int, float)): 
                                st.markdown(f"{icone} **{result_value:.2f}{unidade}**")
                            else: 
                                st.write('N/A')
                        with cols_data[len(selected_indicator["variaveis"])+2]: 
                            st.write(result.get('observacao', 'N/A'))
                        with cols_data[len(selected_indicator["variaveis"])+3]:
                            analise_critica_dict = result.get('analise_critica', {})
                            status_analise = get_analise_status(analise_critica_dict)
                            st.write(status_analise)
                            if any(analise_critica_dict.get(key, "").strip() for key in ["what", "why", "who", "when", "where", "how", "howMuch"]):
                                with st.expander("Ver Análise"):
                                    st.markdown("**O que:** " + analise_critica_dict.get("what", ""))
                                    st.markdown("**Por que:** " + analise_critica_dict.get("why", ""))
                                    st.markdown("**Quem:** " + analise_critica_dict.get("who", ""))
                                    st.markdown("**Quando:** " + analise_critica_dict.get("when", ""))
                                    st.markdown("**Onde:** " + analise_critica_dict.get("where", ""))
                                    st.markdown("**Como:** " + analise_critica_dict.get("how", ""))
                                    st.markdown("**Quanto custa:** " + analise_critica_dict.get("howMuch", ""))
                        with cols_data[len(selected_indicator["variaveis"])+4]:
                            if st.button("🗑️", key=f"delete_result_{result.get('data_referencia')}"):
                                delete_result(selected_indicator['id'], data_referencia, st.session_state.username)
                    else: 
                        st.warning("Resultado com data de referência ausente. Impossível exibir/excluir.")
            else:
                # Aqui está a linha problemática, corrigida com quebras de linha
                col1, col2, col3, col4, col5, col6 = st.columns([2, 1, 2, 2, 2, 1])
                with col1: 
                    st.markdown("**Período**")
                with col2: 
                    st.markdown(f"**Resultado ({unidade_display})**")
                with col3: 
                    st.markdown("**Observações**")
                with col4: 
                    st.markdown("**Análise Crítica**")
                with col5: 
                    st.markdown("**Data de Atualização**")
                with col6: 
                    st.markdown("**Ações**")
                
                for result in indicator_results_sorted:
                    data_referencia = result.get('data_referencia')
                    if data_referencia:
                        col1, col2, col3, col4, col5, col6 = st.columns([2, 1, 2, 2, 2, 1])
                        with col1: 
                            st.write(pd.to_datetime(data_referencia).strftime("%B/%Y"))
                        with col2:
                            result_value = result.get('resultado')
                            if isinstance(result_value, (int, float)): 
                                st.write(f"{result_value:.2f}{unidade_display}")
                            else: 
                                st.write('N/A')
                        with col3: 
                            st.write(result.get('observacao', 'N/A'))
                        with col4:
                            analise_critica_dict = result.get('analise_critica', {})
                            status_analise = get_analise_status(analise_critica_dict)
                            st.write(status_analise)
                            if any(analise_critica_dict.get(key, "").strip() for key in ["what", "why", "who", "when", "where", "how", "howMuch"]):
                                with st.expander("Ver Análise"):
                                    st.markdown("**O que:** " + analise_critica_dict.get("what", ""))
                                    st.markdown("**Por que:** " + analise_critica_dict.get("why", ""))
                                    st.markdown("**Quem:** " + analise_critica_dict.get("who", ""))
                                    st.markdown("**Quando:** " + analise_critica_dict.get("when", ""))
                                    st.markdown("**Onde:** " + analise_critica_dict.get("where", ""))
                                    st.markdown("**Como:** " + analise_critica_dict.get("how", ""))
                                    st.markdown("**Quanto custa:** " + analise_critica_dict.get("howMuch", ""))
                        with col5: 
                            st.write(pd.to_datetime(result.get('data_atualizacao')).strftime("%d/%m/%Y %H:%M") if result.get('data_atualizacao') else 'N/A')
                        with col6:
                            if st.button("🗑️", key=f"delete_result_{result.get('data_referencia')}"):
                                delete_result(selected_indicator['id'], data_referencia, st.session_state.username)
                    else: 
                        st.warning("Resultado com data de referência ausente. Impossível exibir/excluir.")
        else: 
            st.info("Nenhum resultado registrado para este indicador.")

        st.markdown("---")
        all_results = load_results()
        log_results = [r for r in all_results if r["indicator_id"] == selected_indicator["id"]]
        log_results = sorted(log_results, key=lambda x: x.get("data_atualizacao", ""), reverse=True)

        with st.expander("📜 Log de Preenchimentos (clique para visualizar)", expanded=False):
            if log_results:
                log_data_list = []
                unidade_log = selected_indicator.get('unidade', '')
                for r in log_results:
                    result_saved_display = r.get("resultado")
                    if isinstance(result_saved_display, (int, float)): 
                        result_saved_display = f"{result_saved_display:.2f}{unidade_log}"
                    else: 
                        result_saved_display = "N/A"
                    valores_vars = r.get("valores_variaveis", {})
                    if valores_vars: 
                        valores_vars_display = ", ".join([f"{v}={float(val):.2f}" if isinstance(val, (int, float)) else f"{v}={val}" for v, val in valores_vars.items()])
                    else: 
                        valores_vars_display = "N/A"
                    log_entry = {
                        "Período": pd.to_datetime(r.get("data_referencia")).strftime("%B/%Y") if r.get("data_referencia") else "N/A",
                        "Resultado Salvo": result_saved_display,
                        "Valores Variáveis": valores_vars_display,
                        "Usuário": r.get("usuario", "System"),
                        "Status Análise Crítica": get_analise_status(r.get("analise_critica", {})),
                        "Data/Hora Preenchimento": pd.to_datetime(r.get("data_atualizacao", r.get("data_criacao", datetime.now().isoformat()))).strftime("%d/%m/%Y %H:%M")
                    }
                    log_data_list.append(log_entry)
                log_df = pd.DataFrame(log_data_list)
                cols_order = ["Período", "Resultado Salvo", "Valores Variáveis", "Usuário", "Status Análise Crítica", "Data/Hora Preenchimento"]
                log_df = log_df[cols_order]
                st.dataframe(log_df, use_container_width=True)
            else: 
                st.info("Nenhum registro de preenchimento encontrado para este indicador.")
    st.markdown('</div>', unsafe_allow_html=True)
    
def get_analise_status(analise_dict):
    """Função auxiliar para verificar o status de preenchimento da análise crítica."""
    if not analise_dict or analise_dict == {}:
        return "❌ Não preenchida"

    if "status_preenchimento" in analise_dict:
        return analise_dict["status_preenchimento"]

    campos_relevantes = ["what", "why", "who", "when", "where", "how", "howMuch"]
    campos_preenchidos = sum(1 for campo in campos_relevantes if campo in analise_dict and analise_dict[campo] and analise_dict[campo].strip())
    total_campos = len(campos_relevantes)

    if campos_preenchidos == 0: return "❌ Não preenchida"
    elif campos_preenchidos == total_campos: return "✅ Preenchida completamente"
    else: return f"⚠️ Preenchida parcialmente ({campos_preenchidos}/{total_campos})"

def show_dashboard(SETORES, TEMA_PADRAO):
    """Mostra o dashboard de indicadores."""
    st.markdown('<div class="dashboard-card">', unsafe_allow_html=True)
    st.header("Dashboard de Indicadores")
    indicators = load_indicators()
    results = load_results()

    if not indicators:
        st.info("Nenhum indicador cadastrado. Utilize a opção 'Criar Indicador' para começar.")
        st.markdown('</div>', unsafe_allow_html=True)
        return

    col1, col2 = st.columns(2)
    with col1:
        if st.session_state.user_type == "Operador" and st.session_state.user_sector != "Todos":
            setor_filtro = st.session_state.user_sector
            st.info(f"Visualizando indicadores do setor: {setor_filtro}")
        else:
            setores_disponiveis = ["Todos"] + sorted(list(set(ind["responsavel"] for ind in indicators)))
            setor_filtro = st.selectbox("Filtrar por Setor:", setores_disponiveis)
    with col2:
        status_options = ["Todos", "Acima da Meta", "Abaixo da Meta", "Sem Resultados"]
        status_filtro = st.multiselect("Filtrar por Status:", status_options, default=["Todos"])

    if setor_filtro != "Todos": filtered_indicators = [ind for ind in indicators if ind["responsavel"] == setor_filtro]
    else: filtered_indicators = indicators
    if not filtered_indicators: st.warning(f"Nenhum indicador encontrado para o setor {setor_filtro}.\n"); st.markdown('</div>', unsafe_allow_html=True); return

    st.subheader("Resumo dos Indicadores")
    total_indicators = len(filtered_indicators); indicators_with_results = 0; indicators_above_target = 0; indicators_below_target = 0
    for ind in filtered_indicators:
        ind_results = [r for r in results if r["indicator_id"] == ind["id"]]
        if ind_results:
            df_results = pd.DataFrame(ind_results); df_results["data_referencia"] = pd.to_datetime(df_results["data_referencia"]); df_results = df_results.sort_values("data_referencia", ascending=False)
            last_result = float(df_results.iloc[0]["resultado"]); meta = float(ind.get("meta", 0.0))
            if ind["comparacao"] == "Maior é melhor":
                if last_result >= meta: indicators_above_target += 1
                else: indicators_below_target += 1
            else:
                if last_result <= meta: indicators_above_target += 1
                else: indicators_below_target += 1

    col1, col2, col3, col4 = st.columns(4)
    with col1: st.markdown(f"""<div style="background-color:#f8f9fa; padding:15px; border-radius:5px; text-align:center;"><h3 style="margin:0; color:#1E88E5;">{total_indicators}</h3><p style="margin:0;">Total de Indicadores</p></div>""", unsafe_allow_html=True)
    with col2: st.markdown(f"""<div style="background-color:#f8f9fa; padding:15px; border-radius:5px; text-align:center;"><h3 style="margin:0; color:#1E88E5;">{indicators_with_results}</h3><p style="margin:0;">Com Resultados</p></div>""", unsafe_allow_html=True)
    with col3: st.markdown(f"""<div style="background-color:#26A69A; padding:15px; border-radius:5px; text-align:center;"><h3 style="margin:0; color:white;">{indicators_above_target}</h3><p style="margin:0; color:white;">Acima da Meta</p></div>""", unsafe_allow_html=True)
    with col4: st.markdown(f"""<div style="background-color:#FF5252; padding:15px; border-radius:5px; text-align:center;"><h3 style="margin:0; color:white;">{indicators_below_target}</h3><p style="margin:0; color:white;">Abaixo da Meta</p></div>""", unsafe_allow_html=True)

    st.subheader("Status dos Indicadores")
    status_data = {"Status": ["Acima da Meta", "Abaixo da Meta", "Sem Resultados"], "Quantidade": [indicators_above_target, indicators_below_target, total_indicators - indicators_with_results]}
    df_status = pd.DataFrame(status_data)
    fig_status = px.pie(df_status, names="Status", values="Quantidade", title="Distribuição de Status dos Indicadores", color="Status", color_discrete_map={"Acima da Meta": "#26A69A", "Abaixo da Meta": "#FF5252", "Sem Resultados": "#9E9E9E"})
    st.plotly_chart(fig_status, use_container_width=True)

    st.subheader("Indicadores")
    indicator_data = []
    for ind in filtered_indicators:
        ind_results = [r for r in results if r["indicator_id"] == ind["id"]]
        if ind_results:
            df_results = pd.DataFrame(ind_results); df_results["data_referencia"] = pd.to_datetime(df_results["data_referencia"]); df_results = df_results.sort_values("data_referencia", ascending=False)
            last_result = df_results.iloc[0]["resultado"]; last_date = df_results.iloc[0]["data_referencia"]
            try:
                meta = float(ind.get("meta", 0.0)); resultado = float(last_result)
                if ind["comparacao"] == "Maior é melhor": status = "Acima da Meta" if resultado >= meta else "Abaixo da Meta"
                else: status = "Acima da Meta" if resultado <= meta else "Abaixo da Meta"
                if meta != 0:
                    variacao = ((resultado / meta) - 1) * 100
                    if ind["comparacao"] == "Menor é melhor": variacao = -variacao
                else: variacao = float('inf') if resultado > 0 else (float('-inf') if resultado < 0 else 0)
            except: status = "N/A"; variacao = 0
            data_formatada = format_date_as_month_year(last_date)
        else: last_result = "N/A"; data_formatada = "N/A"; status = "Sem Resultados"; variacao = 0
        indicator_data.append({"indicator": ind, "last_result": last_result, "data_formatada": data_formatada, "status": status, "variacao": variacao, "results": ind_results})

    if status_filtro and "Todos" not in status_filtro: indicator_data = [d for d in indicator_data if d["status"] in status_filtro]
    if not indicator_data: st.warning("Nenhum indicador encontrado com os filtros selecionados."); st.markdown('</div>', unsafe_allow_html=True); return

    for i, data in enumerate(indicator_data):
        ind = data["indicator"]; unidade_display = ind.get('unidade', '')
        st.markdown(f"""<div style="background-color:#f8f9fa; padding:15px; border-radius:5px; margin-bottom:20px;"><h3 style="margin:0; color:#1E88E5;">{ind['nome']}</h3><p style="margin:5px 0; color:#546E7A;">Setor: {ind['responsavel']}</p></div>""", unsafe_allow_html=True)
        if data["results"]:
            fig = create_chart(ind["id"], ind["tipo_grafico"], TEMA_PADRAO)
            st.plotly_chart(fig, use_container_width=True)
            col1, col2, col3 = st.columns(3)
            with col1:
                meta_display = f"{float(ind.get('meta', 0.0)):.2f}{unidade_display}"
                st.markdown(f"""<div style="background-color:white; padding:10px; border-radius:5px; text-align:center; border:1px solid #e0e0e0;"><p style="margin:0; font-size:12px; color:#666;">Meta</p><p style="margin:0; font-weight:bold; font-size:18px;">{meta_display}</p></div>""", unsafe_allow_html=True)
            with col2:
                status_color = "#26A69A" if data["status"] == "Acima da Meta" else "#FF5252"
                last_result_display = f"{float(data['last_result']):.2f}{unidade_display}" if isinstance(data['last_result'], (int, float)) else "N/A"
                st.markdown(f"""<div style="background-color:white; padding:10px; border-radius:5px; text-align:center; border:1px solid #e0e0e0;"><p style="margin:0; font-size:12px; color:#666;">Último Resultado</p><p style="margin:0; font-weight:bold; font-size:18px; color:{status_color};">{last_result_display}</p></div>""", unsafe_allow_html=True)
            with col3:
                variacao_color = "#26A69A" if (data["variacao"] >= 0 and ind["comparacao"] == "Maior é melhor") or (data["variacao"] <= 0 and ind["comparacao"] == "Menor é melhor") else "#FF5252"
                if data['variacao'] == float('inf'): variacao_text = "+∞%"; variacao_color = "#26A69A" if ind["comparacao"] == "Maior é melhor" else "#FF5252"
                elif data['variacao'] == float('-inf'): variacao_text = "-∞%"; variacao_color = "#26A69A" if ind["comparacao"] == "Menor é melhor" else "#FF5252"
                elif isinstance(data['variacao'], (int, float)): variacao_text = f"{data['variacao']:.2f}%"
                else: variacao_text = "N/A"
                st.markdown(f"""<div style="background-color:white; padding:10px; border-radius:5px; text-align:center; border:1px solid #e0e0e0;"><p style="margin:0; font-size:12px; color:#666;">Variação vs Meta</p><p style="margin:0; font-weight:bold; font-size:18px; color:{variacao_color};">{variacao_text}</p></div>""", unsafe_allow_html=True)

            with st.expander("Ver Série Histórica e Análise Crítica"):
                if data["results"]:
                    df_hist = pd.DataFrame(data["results"]); df_hist["data_referencia"] = pd.to_datetime(df_hist["data_referencia"]); df_hist = df_hist.sort_values("data_referencia", ascending=False)
                    df_hist["status"] = df_hist.apply(lambda row: "Acima da Meta" if (float(row["resultado"]) >= float(ind.get("meta", 0.0)) and ind["comparacao"] == "Maior é melhor") or (float(row["resultado"]) <= float(ind.get("meta", 0.0)) and ind["comparacao"] == "Menor é melhor") else "Abaixo da Meta", axis=1)
                    df_display = df_hist[["data_referencia", "resultado", "status"]].copy(); df_display["resultado"] = df_display["resultado"].apply(lambda x: f"{float(x):.2f}{unidade_display}" if isinstance(x, (int, float)) else "N/A")
                    if "observacao" in df_hist.columns: df_display["observacao"] = df_hist["observacao"]
                    else: df_display["observacao"] = ""
                    df_display["data_referencia"] = df_display["data_referencia"].apply(lambda x: x.strftime("%d/%m/%Y"))
                    df_display.columns = ["Data de Referência", f"Resultado ({unidade_display})", "Status", "Observações"]
                    st.dataframe(df_display, use_container_width=True)

                    if len(df_hist) > 1:
                        ultimos_resultados = df_hist.sort_values("data_referencia")["resultado"].astype(float).tolist()
                        if len(ultimos_resultados) >= 3:
                            if ind["comparacao"] == "Maior é melhor":
                                tendencia = "crescente" if ultimos_resultados[-1] > ultimos_resultados[-2] > ultimos_resultados[-3] else "decrescente" if ultimos_resultados[-1] < ultimos_resultados[-2] < ultimos_resultados[-3] else "estável"
                            else:
                                tendencia = "crescente" if ultimos_resultados[-1] < ultimos_resultados[-2] < ultimos_resultados[-3] else "decrescente" if ultimos_resultados[-1] > ultimos_resultados[-2] > ultimos_resultados[-3] else "estável"
                            tendencia_color = "#26A69A" if (tendencia == "crescente" and ind["comparacao"] == "Maior é melhor") or (tendencia == "decrescente" and ind["comparacao"] == "Menor é melhor") else "#FF5252" if (tendencia == "decrescente" and ind["comparacao"] == "Maior é melhor") or (tendencia == "crescente" and ind["comparacao"] == "Menor é melhor") else "#FFC107"
                            st.markdown(f"""<div style="margin-top:15px;"><h4>Análise de Tendência</h4><p>Este indicador apresenta uma tendência <span style="color:{tendencia_color}; font-weight:bold;">{tendencia}</span> nos últimos 3 períodos.</p></div>""", unsafe_allow_html=True)
                            st.markdown("<h4>Análise Automática</h4>", unsafe_allow_html=True)
                            meta_float = float(ind.get("meta", 0.0))
                            last_result_float = float(data["last_result"]) if isinstance(data["last_result"], (int, float)) else None
                            if last_result_float is not None:
                                if tendencia == "crescente" and ind["comparacao"] == "Maior é melhor":
                                    st.success("O indicador apresenta evolução positiva, com resultados crescentes nos últimos períodos.")
                                    if last_result_float >= meta_float:
                                        st.success("O resultado atual está acima da meta estabelecida, demonstrando bom desempenho.")
                                    else:
                                        st.warning("Apesar da evolução positiva, o resultado ainda está abaixo da meta estabelecida.")
                                elif tendencia == "decrescente" and ind["comparacao"] == "Maior é melhor":
                                    st.error("O indicador apresenta tendência de queda, o que é preocupante para este tipo de métrica.")
                                    if last_result_float >= meta_float:
                                        st.warning("Embora o resultado atual ainda esteja acima da meta, a tendência de queda requer atenção.")
                                    else:
                                        st.error("O resultado está abaixo da meta e com tendência de queda, exigindo ações corretivas urgentes.")
                                elif tendencia == "crescente" and ind["comparacao"] == "Menor é melhor":
                                    st.error("O indicador apresenta tendência de aumento, o que é negativo para este tipo de métrica.")
                                    if last_result_float <= meta_float:
                                        st.warning("Embora o resultado atual ainda esteja dentro da meta, a tendência de aumento requer atenção.")
                                    else:
                                        st.error("O resultado está acima da meta e com tendência de aumento, exigindo ações corretivas urgentes.")
                                elif tendencia == "decrescente" and ind["comparacao"] == "Menor é melhor":
                                    st.success("O indicador apresenta evolução positiva, com resultados decrescentes nos últimos períodos.")
                                    if last_result_float <= meta_float:
                                        st.success("O resultado atual está dentro da meta estabelecida, demonstrando bom desempenho.")
                                    else:
                                        st.warning("Apesar da evolução positiva, o resultado ainda está acima da meta estabelecida.")
                                else:
                                    if (last_result_float >= meta_float and ind["comparacao"] == "Maior é melhor") or (last_result_float <= meta_float and ind["comparacao"] == "Menor é melhor"):
                                        st.info("O indicador apresenta estabilidade e está dentro da meta estabelecida.")
                                    else:
                                        st.warning("O indicador apresenta estabilidade, porém está fora da meta estabelecida.")
                            else:
                                st.info("Não foi possível realizar a análise automática devido a dados de resultado inválidos.")
                        else: st.info("Não há dados suficientes para análise de tendência (mínimo de 3 períodos necessários).")
                    else: st.info("Não há dados históricos suficientes para análise de tendência.")

                    st.markdown("<h4>Análise Crítica 5W2H</h4>", unsafe_allow_html=True)
                    ultimo_resultado = df_hist.iloc[0]
                    has_analysis = False
                    if "analise_critica" in ultimo_resultado:
                        analise_dict = ultimo_resultado["analise_critica"]
                        has_analysis = analise_dict is not None and analise_dict != {}

                    if has_analysis:
                        st.markdown("**O que (What):** " + analise_dict.get("what", ""))
                        st.markdown("**Por que (Why):** " + analise_dict.get("why", ""))
                        st.markdown("**Quem (Who):** " + analise_dict.get("who", ""))
                        st.markdown("**Quando (When):** " + analise_dict.get("when", ""))
                        st.markdown("**Onde (Where):** " + analise_dict.get("where", ""))
                        st.markdown("**Como (How):** " + analise_dict.get("how", ""))
                        st.markdown("**Quanto custa (How Much):** " + analise_dict.get("howMuch", ""))
                    else:
                        st.info("Não há análise crítica registrada para o último resultado. Utilize a opção 'Preencher Indicador' para adicionar uma análise crítica no formato 5W2H.")
                        with st.expander("O que é a análise 5W2H?"):
                            st.markdown("""**5W2H** é uma metodologia de análise que ajuda a estruturar o pensamento crítico sobre um problema ou situação: - **What (O quê)**: O que está acontecendo? Qual é o problema ou situação? - **Why (Por quê)**: Por que isso está acontecendo? Quais são as causas? - **Who (Quem)**: Quem é responsável? Quem está envolvido? - **When (Quando)**: Quando isso aconteceu? Qual é o prazo para resolução? - **Where (Onde)**: Onde ocorre o problema? Em qual setor ou processo? - **How (Como)**: Como resolver o problema? Quais ações devem ser tomadas? - **How Much (Quanto custa)**: Quanto custará implementar a solução? Quais recursos são necessários? Esta metodologia ajuda a garantir que todos os aspectos importantes sejam considerados na análise e no plano de ação.""")
                else: st.info("Não há resultados registrados para este indicador.")
        else:
            st.info("Este indicador ainda não possui resultados registrados.")
            meta_display = f"{float(ind.get('meta', 0.0)):.2f}{unidade_display}"
            st.markdown(f"""<div style="background-color:white; padding:10px; border-radius:5px; text-align:center; border:1px solid #e0e0e0; width: 200px; margin: 10px auto;"><p style="margin:0; font-size:12px; color:#666;">Meta</p><p style="margin:0; font-weight:bold; font-size:18px;">{meta_display}</p></div>""", unsafe_allow_html=True)
        st.markdown("<hr style='margin: 30px 0; border-color: #e0e0e0;'>", unsafe_allow_html=True)

    if st.button("📤 Exportar Tudo"):
        export_data = []
        for data in indicator_data:
            ind = data["indicator"]; unidade_export = ind.get('unidade', '')
            last_result_export = f"{float(data['last_result']):.2f}{unidade_export}" if isinstance(data['last_result'], (int, float)) else "N/A"
            meta_export = f"{float(ind.get('meta', 0.0)):.2f}{unidade_export}"
            if data['variacao'] == float('inf'): variacao_export = "+Inf"
            elif data['variacao'] == float('-inf'): variacao_export = "-Inf"
            elif isinstance(data['variacao'], (int, float)): variacao_export = f"{data['variacao']:.2f}%"
            else: variacao_export = "N/A"
            export_data.append({"Nome": ind["nome"], "Setor": ind["responsavel"], "Meta": meta_export, "Último Resultado": last_result_export, "Período": data["data_formatada"], "Status": data["status"], "Variação": variacao_export})
        df_export = pd.DataFrame(export_data)
        download_link = get_download_link(df_export, "indicadores_dashboard.xlsx")
        st.markdown(download_link, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

def show_overview():
    """Mostra a visão geral dos indicadores."""
    st.markdown('<div class="dashboard-card">', unsafe_allow_html=True)
    st.header("Visão Geral dos Indicadores")
    indicators = load_indicators()
    results = load_results()

    if not indicators:
        st.info("Nenhum indicador cadastrado. Utilize a opção 'Criar Indicador' para começar.")
        st.markdown('</div>', unsafe_allow_html=True)
        return

    col1, col2 = st.columns(2)
    with col1:
        setores_disponiveis = sorted(list(set([ind["responsavel"] for ind in indicators])))
        setor_filtro = st.multiselect("Filtrar por Setor", options=["Todos"] + setores_disponiveis, default=["Todos"])
    with col2:
        status_filtro = st.multiselect("Status", options=["Todos", "Acima da Meta", "Abaixo da Meta", "Sem Resultados"], default=["Todos"])
    search_query = st.text_input("Buscar indicador por nome ou setor", placeholder="Digite para buscar...")

    filtered_indicators = indicators
    if setor_filtro and "Todos" not in setor_filtro: filtered_indicators = [ind for ind in filtered_indicators if ind["responsavel"] in setor_filtro]

    overview_data = []
    for ind in filtered_indicators:
        ind_results = [r for r in results if r["indicator_id"] == ind["id"]]
        unidade_display = ind.get('unidade', '')
        if ind_results:
            df_results = pd.DataFrame(ind_results); df_results["data_referencia"] = pd.to_datetime(df_results["data_referencia"]); df_results = df_results.sort_values("data_referencia", ascending=False)
            last_result = df_results.iloc[0]["resultado"]; last_date = df_results.iloc[0]["data_referencia"]
            try:
                meta = float(ind.get("meta", 0.0)); resultado = float(last_result)
                if ind["comparacao"] == "Maior é melhor": status = "Acima da Meta" if resultado >= meta else "Abaixo da Meta"
                else: status = "Acima da Meta" if resultado <= meta else "Abaixo da Meta"
                if meta != 0.0:
                    variacao = ((resultado / meta) - 1) * 100
                    if ind["comparacao"] == "Menor é melhor": variacao = -variacao
                else: variacao = float('inf') if resultado > 0 else (float('-inf') if resultado < 0 else 0)
            except: status = "N/A"; variacao = 0
            data_formatada = format_date_as_month_year(last_date)
            last_result_formatted = f"{float(last_result):.2f}{unidade_display}" if isinstance(last_result, (int, float)) else "N/A"
            meta_formatted = f"{float(meta):.2f}{unidade_display}"
            if variacao == float('inf'): variacao_formatted = "+Inf"
            elif variacao == float('-inf'): variacao_formatted = "-Inf"
            elif isinstance(variacao, (int, float)): variacao_formatted = f"{variacao:.2f}%"
            else: variacao_formatted = "N/A"
        else:
            last_result_formatted = "N/A"; data_formatada = "N/A"; status = "Sem Resultados"; variacao_formatted = "N/A"
            meta_formatted = f"{float(ind.get('meta', 0.0)):.2f}{unidade_display}"
        overview_data.append({"Nome": ind["nome"], "Setor": ind["responsavel"], "Meta": meta_formatted, "Último Resultado": last_result_formatted, "Período": data_formatada, "Status": status, "Variação": variacao_formatted})

    if status_filtro and "Todos" not in status_filtro: overview_data = [d for d in overview_data if d["Status"] in status_filtro]
    if search_query:
        search_query_lower = search_query.lower()
        overview_data = [d for d in overview_data if search_query_lower in d["Nome"].lower() or search_query_lower in d["Setor"].lower()]

    df_overview = pd.DataFrame(overview_data)
    if not df_overview.empty:
        df_overview.rename(columns={'Variação': 'Variação (%)'}, inplace=True)
        st.dataframe(df_overview, use_container_width=True)
        if st.button("📤 Exportar para Excel"):
            df_export = pd.DataFrame(overview_data); df_export.rename(columns={'Variação': 'Variação (%)'}, inplace=True)
            download_link = get_download_link(df_export, "visao_geral_indicadores.xlsx")
            st.markdown(download_link, unsafe_allow_html=True)
        st.subheader("Resumo por Setor")
        setor_counts = df_overview["Setor"].value_counts().reset_index(); setor_counts.columns = ["Setor", "Quantidade de Indicadores"]
        fig_setor = px.bar(setor_counts, x="Setor", y="Quantidade de Indicadores", title="Quantidade de Indicadores por Setor", color="Setor")
        st.plotly_chart(fig_setor, use_container_width=True)
        st.subheader("Status dos Indicadores")
        status_counts = df_overview["Status"].value_counts().reset_index(); status_counts.columns = ["Status", "Quantidade"]
        fig_status = px.pie(status_counts, names="Status", values="Quantidade", title="Distribuição de Status dos Indicadores", color="Status", color_discrete_map={"Acima da Meta": "#26A69A", "Abaixo da Meta": "#FF5252", "Sem Resultados": "#9E9E9E"})
        st.plotly_chart(fig_status, use_container_width=True)
    else: st.warning("Nenhum indicador encontrado com os filtros selecionados.")
    st.markdown('</div>', unsafe_allow_html=True)

def show_settings():
    """Mostra a página de configurações."""
    # Declare a variável global no início da função, antes de qualquer uso
    global KEY_FILE
    
    st.markdown('<div class="dashboard-card">', unsafe_allow_html=True)
    st.header("Configurações")

    config = load_config()

    st.subheader("Informações do Sistema")
    col1, col2 = st.columns(2)
    with col1: st.markdown("""**Versão do Portal:** 1.2.0\n**Data da Última Atualização:** 22/04/2025\n**Desenvolvido por:** Equipe de Desenvolvimento""")
    with col2: st.markdown("""**Suporte Técnico:**\nEmail: suporte@portalindicadores.com\nTelefone: (11) 1234-5678""")

    st.subheader("Backup Automático")
    if "backup_hour" not in config: config["backup_hour"] = "00:00"
    try: backup_hour = datetime.strptime(config["backup_hour"], "%H:%M").time()
    except ValueError: config["backup_hour"] = "00:00"; save_config(config); backup_hour = datetime.time(0, 0)
    new_backup_hour = st.time_input("Horário do backup automático", backup_hour)

    if new_backup_hour != backup_hour:
        config["backup_hour"] = new_backup_hour.strftime("%H:%M")
        save_config(config)
        st.success("Horário de backup automático atualizado com sucesso!")

    if "last_backup_date" in config: st.markdown(f"**Último backup automático:** {config['last_backup_date']}")
    else: st.markdown("**Último backup automático:** Nunca executado")

    st.warning("As funcionalidades de backup e restauração precisam ser adaptadas para o banco de dados PostgreSQL.")
    st.info("Para backup do banco de dados, a ferramenta `pg_dump` é a mais recomendada.")
    st.info("Para restaurar, `pg_restore` ou `psql` podem ser usados.")

    # Botão para criar backup manual (fora do expander)
    if st.button("⟳ Criar novo backup manual", help="Cria um backup manual de todos os dados do sistema."):
        with st.spinner("Criando backup manual..."):
            # Não precisa declarar global aqui, já foi declarado no início da função
            generate_key(KEY_FILE)
            cipher = initialize_cipher(KEY_FILE)
            backup_file = backup_data(cipher, tipo_backup="user")
            if backup_file:
                st.success(f"Backup manual criado: {backup_file}")
            else:
                st.error("Falha ao criar o backup manual.")

    # Botão para restaurar backup (fora do expander)
    if not os.path.exists("backups"):
        os.makedirs("backups")
    backup_files = [f for f in os.listdir("backups") if f.startswith("backup_") and f.endswith(".bkp")]
    if backup_files:
        selected_backup = st.selectbox("Selecione o backup para restaurar", backup_files)
        if st.button("⚙️ Restaurar arquivo de backup ️", help="Restaura os dados do sistema a partir de um arquivo de backup."):
            with st.spinner("Criando backup de segurança..."):
                # Não precisa declarar global aqui, já foi declarado no início da função
                generate_key(KEY_FILE)
                cipher = initialize_cipher(KEY_FILE)
                backup_file_antes_restauracao = backup_data(cipher, tipo_backup="seguranca")
                if backup_file_antes_restauracao:
                    st.success(f"Backup de segurança criado: {backup_file_antes_restauracao}")
                else:
                    st.error("Falha ao criar o backup de segurança.")

            try:
                with st.spinner("Restaurando backup..."):
                    if restore_data(os.path.join("backups", selected_backup), cipher):
                        st.success("Backup restaurado com sucesso!")
                    else:
                        st.error("Falha ao restaurar o backup.")
            except Exception as e:
                st.error(f"Ocorreu um erro durante a restauração: {e}")
    else:
        st.info("Nenhum arquivo de backup encontrado.")

    if st.session_state.username == "admin":
        st.subheader("Administração do Sistema")
        with st.expander("Opções Avançadas de Limpeza"):
            st.warning("⚠️ Estas opções podem causar perda de dados. Use com cuidado.")
            if st.button("🗑️ Limpar resultados", help="Exclui todos os resultados dos indicadores."):
                if "confirm_limpar_resultados" not in st.session_state: st.session_state.confirm_limpar_resultados = False
                if not st.session_state.confirm_limpar_resultados:
                    st.warning("Tem certeza que deseja limpar todos os resultados? Esta ação não pode ser desfeita.")
                    st.session_state.confirm_limpar_resultados = True; st.rerun()
                else:
                    with st.spinner("Limpando resultados..."):
                        conn = get_db_connection()
                        if conn:
                            try:
                                cur = conn.cursor(); cur.execute("DELETE FROM resultados;"); conn.commit()
                                st.success("Resultados excluídos com sucesso!")
                            except Exception as e: st.error(f"Erro ao excluir resultados: {e}"); conn.rollback()
                            finally: cur.close(); conn.close()
                        st.session_state.confirm_limpar_resultados = False
            if st.button("🧹 Excluir tudo!", help="Exclui todos os indicadores e resultados do sistema."):
                if "confirm_limpar_tudo" not in st.session_state: st.session_state.confirm_limpar_tudo = False
                if not st.session_state.confirm_limpar_tudo:
                    st.warning("Tem certeza que deseja limpar todos os indicadores e resultados? Esta ação não pode ser desfeita.")
                    st.session_state.confirm_limpar_tudo = True; st.rerun()
                else:
                    with st.spinner("Limpando tudo..."):
                        conn = get_db_connection()
                        if conn:
                            try:
                                cur = conn.cursor(); cur.execute("DELETE FROM indicadores;"); conn.commit()
                                st.success("Indicadores e resultados excluídos com sucesso!")
                            except Exception as e: st.error(f"Erro ao excluir indicadores e resultados: {e}"); conn.rollback()
                            finally: cur.close(); conn.close()
                        st.session_state.confirm_limpar_tudo = False
    st.markdown('</div>', unsafe_allow_html=True)

def show_user_management(SETORES):
    """Mostra a página de gerenciamento de usuários."""
    st.markdown('<div class="dashboard-card">', unsafe_allow_html=True)
    st.header("Gerenciamento de Usuários")
    users = load_users()

    migrated = False
    for user, data in list(users.items()):
        if not isinstance(data, dict):
            users[user] = {"password": data, "tipo": "Administrador" if user == "admin" else "Visualizador", "setor": "Todos", "nome_completo": "", "email": ""}
            migrated = True
        elif "setor" not in data: users[user]["setor"] = "Todos"; migrated = True
        elif "nome_completo" not in data: users[user]["nome_completo"] = ""; migrated = True
        elif "email" not in data: users[user]["email"] = ""; migrated = True
    if migrated: save_users(users); st.success("Dados de usuários foram atualizados para o novo formato.")

    total_users = len(users); admin_count = sum(1 for user, data in users.items() if isinstance(data, dict) and data.get("tipo") == "Administrador")
    operator_count = sum(1 for user, data in users.items() if isinstance(data, dict) and data.get("tipo") == "Operador")
    viewer_count = sum(1 for user, data in users.items() if isinstance(data, dict) and data.get("tipo") == "Visualizador")

    st.subheader("Visão Geral de Usuários")
    col1, col2, col3, col4 = st.columns(4)
    with col1: st.markdown(f"""<div style="background-color:#f8f9fa; padding:15px; border-radius:5px; text-align:center;"><h3 style="margin:0; color:#1E88E5;">{total_users}</h3><p style="margin:0;">Total de Usuários</p></div>""", unsafe_allow_html=True)
    with col2: st.markdown(f"""<div style="background-color:#26A69A; padding:15px; border-radius:5px; text-align:center;"><h3 style="margin:0; color:white;">{admin_count}</h3><p style="margin:0; color:white;">Administradores</p></div>""", unsafe_allow_html=True)
    with col3: st.markdown(f"""<div style="background-color:#FFC107; padding:15px; border-radius:5px; text-align:center;"><h3 style="margin:0; color:white;">{operator_count}</h3><p style="margin:0; color:white;">Operadores</p></div>""", unsafe_allow_html=True)
    with col4: st.markdown(f"""<div style="background-color:#7E57C2; padding:15px; border-radius:5px; text-align:center;"><h3 style="margin:0; color:white;">{viewer_count}</h3><p style="margin:0; color:white;">Visualizadores</p></div>""", unsafe_allow_html=True)

    st.subheader("Adicionar Novo Usuário")
    with st.form("add_user_form"):
        st.markdown("#### Informações Pessoais")
        col1, col2 = st.columns(2)
        with col1: nome_completo = st.text_input("Nome Completo", placeholder="Digite o nome completo do usuário")
        with col2: email = st.text_input("Email", placeholder="Digite o email do usuário")
        with col1:
            user_type = st.selectbox("Tipo de Usuário", options=["Administrador", "Operador", "Visualizador"], index=2, help="Administrador: acesso total; Operador: gerencia indicadores de um setor; Visualizador: apenas visualização")
        with col2:
            user_sector = st.selectbox("Setor", options=["Todos"] + SETORES, index=0, help="Para Operadores, define o setor que podem gerenciar. Administradores têm acesso a todos os setores.")
        st.markdown("#### Informações de Acesso")
        col1, col2 = st.columns(2)
        with col1: login = st.text_input("Login", placeholder="Digite o login para acesso ao sistema")
        with col2: new_password = st.text_input("Senha", type="password", placeholder="Digite a senha")
        confirm_password = st.text_input("Confirmar Senha", type="password", placeholder="Confirme a senha")
        st.markdown("""<div style="background-color:#f8f9fa; padding:10px; border-radius:5px; margin-top:10px;"><p style="margin:0; font-size:14px;"><strong>Tipos de usuário:</strong></p><ul style="margin:5px 0 0 15px; padding:0; font-size:13px;"><li><strong>Administrador:</strong> Acesso total ao sistema</li><li><strong>Operador:</strong> Gerencia indicadores de um setor específico</li><li><strong>Visualizador:</strong> Apenas visualiza indicadores e resultados</li></ul></div>""", unsafe_allow_html=True)
        if user_type == "Operador" and user_sector == "Todos": st.warning("⚠️ Operadores devem ser associados a um setor específico.")
        submit = st.form_submit_button("➕ Adicionar")

    if submit:
        if not login or not new_password: st.error("❌ Login e senha são obrigatórios.")
        elif login in users: st.error(f"❌ O login '{login}' já existe.")
        elif new_password != confirm_password: st.error("❌ As senhas não coincidem.")
        elif user_type == "Operador" and user_sector == "Todos": st.error("❌ Operadores devem ser associados a um setor específico.")
        elif not nome_completo: st.error("❌ Nome completo é obrigatório.")
        elif email and "@" not in email: st.error("❌ Formato de email inválido.")
        else:
            users[login] = {"password": hashlib.sha256(new_password.encode()).hexdigest(), "tipo": user_type, "setor": user_sector, "nome_completo": nome_completo, "email": email, "data_criacao": datetime.now().isoformat()}
            save_users(users)
            log_user_action("Usuário criado", login, st.session_state.username)
            st.success(f"✅ Usuário '{nome_completo}' (login: {login}) adicionado com sucesso como {user_type} do setor {user_sector}!")
            time.sleep(1); st.rerun()

    st.subheader("Usuários Cadastrados")
    col1, col2 = st.columns(2)
    with col1: filter_type = st.multiselect("Filtrar por Tipo", options=["Todos", "Administrador", "Operador", "Visualizador"], default=["Todos"])
    with col2: filter_sector = st.multiselect("Filtrar por Setor", options=["Todos"] + SETORES, default=["Todos"])
    search_query = st.text_input("🔍 Buscar usuário por nome, login ou email", placeholder="Digite para buscar...")

    filtered_users = {}
    for user, data in users.items():
        if isinstance(data, dict):
            user_type = data.get("tipo", "Visualizador"); user_sector = data.get("setor", "Todos"); nome_completo = data.get("nome_completo", ""); email = data.get("email", ""); data_criacao = data.get("data_criacao", "N/A")
            if data_criacao != "N/A":
                try: data_criacao = datetime.fromisoformat(data_criacao).strftime("%d/%m/%Y")
                except: pass
        else: user_type = "Administrador" if user == "admin" else "Visualizador"; user_sector = "Todos"; nome_completo = ""; email = ""; data_criacao = "N/A"
        if search_query and search_query.lower() not in user.lower() and search_query.lower() not in nome_completo.lower() and search_query.lower() not in email.lower(): continue
        if ("Todos" in filter_type or user_type in filter_type) and ("Todos" in filter_sector or user_sector in filter_sector): filtered_users[user] = data

    if filtered_users:
        user_data_list = []
        for user, data in filtered_users.items():
            if isinstance(data, dict):
                user_type = data.get("tipo", "Visualizador"); user_sector = data.get("setor", "Todos"); nome_completo = data.get("nome_completo", ""); email = data.get("email", ""); data_criacao = data.get("data_criacao", "N/A")
                if data_criacao != "N/A":
                    try: data_criacao = datetime.fromisoformat(data_criacao).strftime("%d/%m/%Y")
                    except: pass
            else: user_type = "Administrador" if user == "admin" else "Visualizador"; user_sector = "Todos"; nome_completo = ""; email = ""; data_criacao = "N/A"
            if user_type == "Administrador": type_color = "#26A69A"
            elif user_type == "Operador": type_color = "#FFC107"
            else: type_color = "#7E57C2"
            user_data_list.append({"Login": user, "Nome": nome_completo or "Não informado", "Email": email or "Não informado", "Tipo": user_type, "Setor": user_sector, "Criado em": data_criacao, "type_color": type_color, "is_current": user == st.session_state.username, "is_admin": user == "admin"})
        df_users = pd.DataFrame(user_data_list)

        for i, row in df_users.iterrows():
            login = row["Login"]; nome = row["Nome"]; email = row["Email"]; user_type = row["Tipo"]; user_sector = row["Setor"]; type_color = row["type_color"]; is_current = row["is_current"]; is_admin = row["is_admin"]
            st.markdown(f"""<div style="background-color:#f8f9fa; padding:15px; border-radius:5px; margin-bottom:10px; border-left: 4px solid {type_color};"><div style="display:flex; justify-content:space-between; align-items:flex-start;"><div><h3 style="margin:0; color:#37474F;">{nome} {' (você)' if is_current else ''}</h3><p style="margin:5px 0 0 0; color:#546E7A;">Login: <strong>{login}</strong></p><p style="margin:3px 0 0 0; color:#546E7A;">Email: {email}</p><p style="margin:3px 0 0 0; color:#546E7A;">Criado em: {row['Criado em']}</p></div><div><span style="background-color:{type_color}; color:white; padding:5px 10px; border-radius:15px; font-size:12px;">{user_type}</span><span style="background-color:#90A4AE; color:white; padding:5px 10px; border-radius:15px; font-size:12px; margin-left:5px;">{user_sector}</span></div></div></div>""", unsafe_allow_html=True)

            if not is_admin and not is_current:
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("✏️ Editar", key=f"edit_{login}"): st.session_state[f"editing_{login}"] = True
                with col2:
                    if st.button("🗑️ Excluir", key=f"del_{login}"): st.session_state[f"deleting_{login}"] = True

                if st.session_state.get(f"editing_{login}", False):
                    with st.form(key=f"edit_form_{login}"):
                        st.subheader(f"Editar Usuário: {nome}"); st.markdown("#### Informações Pessoais")
                        col1, col2 = st.columns(2)
                        with col1: new_nome = st.text_input("Nome Completo", value=nome if nome != "Não informado" else "", key=f"new_nome_{login}")
                        with col2: new_email = st.text_input("Email", value=email if email != "Não informado" else "", key=f"new_email_{login}")
                        with col1: new_type = st.selectbox("Tipo de Usuário", options=["Administrador", "Operador", "Visualizador"], index=["Administrador", "Operador", "Visualizador"].index(user_type), key=f"new_type_{login}")
                        with col2: new_sector = st.selectbox("Setor", options=["Todos"] + SETORES, index=(["Todos"] + SETORES).index(user_sector) if user_sector in ["Todos"] + SETORES else 0, key=f"new_sector_{login}")
                        st.markdown("#### Informações de Acesso")
                        reset_password = st.checkbox("Redefinir senha", key=f"reset_pwd_{login}")
                        if reset_password:
                            new_password = st.text_input("Nova senha", type="password", key=f"new_pwd_{login}")
                            confirm_password = st.text_input("Confirmar nova senha", type="password", key=f"confirm_pwd_{login}")
                        is_valid = True
                        if new_type == "Operador" and new_sector == "Todos": st.error("❌ Operadores devem ser associados a um setor específico."); is_valid = False
                        if new_email and "@" not in new_email: st.error("❌ Formato de email inválido."); is_valid = False
                        col1, col2 = st.columns(2)
                        with col1: submit = st.form_submit_button("Salvar Alterações")
                        with col2: cancel = st.form_submit_button("Cancelar")

                        if submit and is_valid:
                            if reset_password:
                                if not new_password: st.error("❌ A nova senha é obrigatória."); return
                                if new_password != confirm_password: st.error("❌ As senhas não coincidem."); return
                            if isinstance(users[login], dict):
                                users[login]["tipo"] = new_type; users[login]["setor"] = new_sector; users[login]["nome_completo"] = new_nome; users[login]["email"] = new_email
                                if reset_password: users[login]["password"] = hashlib.sha256(new_password.encode()).hexdigest()
                            else:
                                users[login] = {"password": hashlib.sha256(new_password.encode()).hexdigest() if reset_password else users[login], "tipo": new_type, "setor": new_sector, "nome_completo": new_nome, "email": new_email}
                            save_users(users)
                            st.success(f"✅ Usuário '{new_nome}' atualizado com sucesso!")
                            log_user_action("Usuário atualizado", login, st.session_state.username)
                            del st.session_state[f"editing_{login}"]; time.sleep(1); st.rerun()
                        if cancel: del st.session_state[f"editing_{login}"]; st.rerun()

                if st.session_state.get(f"deleting_{login}", False):
                    st.warning(f"⚠️ Tem certeza que deseja excluir o usuário '{nome}' (login: {login})? Esta ação não pode ser desfeita.")
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("✅ Sim, excluir", key=f"confirm_del_{login}"):
                            delete_user(login, st.session_state.username)
                            st.success(f"✅ Usuário '{nome}' excluído com sucesso!")
                            del st.session_state[f"deleting_{login}"]; time.sleep(1); st.rerun()
                    with col2:
                        if st.button("❌ Cancelar", key=f"cancel_del_{login}"):
                            del st.session_state[f"deleting_{login}"]; st.rerun()
            st.markdown("<hr style='margin: 20px 0; border-color: #e0e0e0;'>", unsafe_allow_html=True)
    else: st.info("Nenhum usuário encontrado com os filtros selecionados.")

    if st.session_state.username == "admin":
        if st.button("📤 Exportar Lista"):
            export_data = []
            for user, data in users.items():
                if isinstance(data, dict):
                    user_type = data.get("tipo", "Visualizador"); user_sector = data.get("setor", "Todos"); nome_completo = data.get("nome_completo", ""); email = data.get("email", ""); data_criacao = data.get("data_criacao", "N/A")
                else: user_type = "Administrador" if user == "admin" else "Visualizador"; user_sector = "Todos"; nome_completo = ""; email = ""; data_criacao = "N/A"
                export_data.append({"Login": user, "Nome Completo": nome_completo, "Email": email, "Tipo": user_type, "Setor": user_sector, "Data de Criação": data_criacao})
            df_export = pd.DataFrame(export_data)
            download_link = get_download_link(df_export, "usuarios_sistema.xlsx")
            st.markdown(download_link, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

def delete_user(username, user_performed):
    """Exclui um usuário do banco de dados."""
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("DELETE FROM usuarios WHERE username = %s;", (username,))
            conn.commit()
            log_user_action("Usuário excluído", username, user_performed)
            return True
        except psycopg2.Error as e:
            print(f"Erro ao excluir usuário do banco de dados: {e}")
            conn.rollback()
            return False
        finally:
            cur.close()
            conn.close()
    return False

def logout():
    """Realiza o logout do usuário."""
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

# --- Funções de Backup e Restauração (Revisadas para DB) ---

KEY_FILE = "secret.key" # Definir a chave de criptografia aqui

def generate_key(key_file):
    """Gera uma nova chave de criptografia se não existir."""
    if not os.path.exists(key_file):
        key = Fernet.generate_key()
        with open(key_file, "wb") as kf:
            kf.write(key)
        return key
    return None

def load_key(key_file):
    """Carrega a chave de criptografia do arquivo."""
    try:
        with open(key_file, "rb") as kf:
            return kf.read()
    except FileNotFoundError:
        st.error("Arquivo de chave não encontrado. Execute a função generate_key primeiro.")
        return None

def initialize_cipher(key_file):
    """Inicializa o objeto Fernet para criptografia."""
    key = load_key(key_file)
    if key:
        return Fernet(key)
    return None

def backup_data(cipher, tipo_backup="user"):
    """Cria um arquivo de backup criptografado com todos os dados do DB."""
    if not cipher:
        st.error("Objeto de criptografia não inicializado.")
        return None

    all_data = {
        "users": load_users(),
        "indicators": load_indicators(),
        "results": load_results(),
        "config": load_config(),
        "backup_log": load_backup_log(),
        "indicator_log": load_indicator_log(),
        "user_log": load_user_log()
    }

    all_data_str = json.dumps(all_data, indent=4, default=str).encode()
    encrypted_data = cipher.encrypt(all_data_str)

    if tipo_backup == "user":
        BACKUP_FILE = os.path.join("backups", f"backup_user_{datetime.now().strftime('%Y%m%d%H%M%S')}.bkp")
    else:
        BACKUP_FILE = os.path.join("backups", f"backup_seguranca_{datetime.now().strftime('%Y%m%d%H%M%S')}.bkp")

    if not os.path.exists("backups"):
        os.makedirs("backups")

    try:
        with open(BACKUP_FILE, "wb") as backup_file:
            backup_file.write(encrypted_data)
        log_backup_action("Backup criado", BACKUP_FILE, st.session_state.username)
        return BACKUP_FILE
    except Exception as e:
        st.error(f"Erro ao criar o backup: {e}")
        return None

def restore_data(backup_file, cipher):
    """Restaura os dados a partir de um arquivo de backup criptografado para o DB."""
    if not cipher:
        st.error("Objeto de criptografia não inicializado.")
        return False

    try:
        with open(backup_file, "rb") as file:
            encrypted_data = file.read()

        decrypted_data_str = cipher.decrypt(encrypted_data).decode()
        restored_data = json.loads(decrypted_data_str)

        save_users(restored_data.get("users", {}))
        save_indicators(restored_data.get("indicators", []))
        save_results(restored_data.get("results", []))
        save_config(restored_data.get("config", {}))
        save_backup_log(restored_data.get("backup_log", []))
        save_indicator_log(restored_data.get("indicator_log", []))
        save_user_log(restored_data.get("user_log", []))

        log_backup_action("Backup restaurado", backup_file, st.session_state.username)
        return True
    except Exception as e:
        st.error(f"Erro ao restaurar o backup: {e}")
        return False

def agendar_backup(cipher):
    """Agenda o backup automático."""
    config = load_config()
    backup_hour = config.get("backup_hour", "00:00")

    schedule.clear()

    schedule.every().day.at(backup_hour).do(backup_job, cipher, tipo_backup="seguranca")

    while True:
        schedule.run_pending()
        time.sleep(60)

def backup_job(cipher, tipo_backup):
    """Função executada pelo agendador de backup."""
    try:
        backup_file = backup_data(cipher, tipo_backup=tipo_backup)
        if backup_file:
            print(f"Backup automático criado: {backup_file}")
            config = load_config()
            config["last_backup_date"] = datetime.now().strftime("%d/%m/%Y %H:%M")
            save_config(config)
            keep_last_backups("backups", 3)
        else:
            print("Falha ao criar o backup automático.")
    except Exception as e:
        print(f"Erro durante o backup: {e}")

def keep_last_backups(BACKUP_DIR, num_backups):
    """Mantém apenas os últimos backups no diretório."""
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)
    backups = sorted([os.path.join(BACKUP_DIR, f) for f in os.listdir(BACKUP_DIR) if f.startswith("backup_") and f.endswith(".bkp")],
                     key=os.path.getmtime, reverse=True)
    if len(backups) > num_backups:
        for backup in backups[num_backups:]:
            try:
                os.remove(backup)
                print(f"Backup removido: {backup}")
            except Exception as e:
                print(f"Erro ao remover backup: {backup} - {e}")

# --- Função Principal da Aplicação Streamlit ---

def main():
    configure_page()
    initialize_session_state()
    configure_locale()

    # --- NOVO: Inicializa as tabelas do banco de dados ---
    create_tables_if_not_exists()

    app_config = load_config()

    MENU_ICONS = define_menu_icons()

    # Inicializar objeto de criptografia para backups .bkp
    generate_key(KEY_FILE)
    cipher = initialize_cipher(KEY_FILE)
    
    if st.session_state.should_scroll_to_top:
        scroll_to_here(0, key='top_of_page')
        st.session_state.should_scroll_to_top = False
    
    if not st.session_state.authenticated:
        show_login_page()
        return

    user_type = get_user_type(st.session_state.username)
    user_sector = get_user_sector(st.session_state.username)

    st.session_state.user_type = user_type
    st.session_state.user_sector = user_sector

    st.markdown("""
    <style>
        .main { background-color: #f8f9fa; padding: 1rem; }
        [data-testid="stToolbar"] { display: none !important; }
        [data-testid="stAppViewContainer"] { border: none !important; }
        footer { display: none !important; }
        #MainMenu { visibility: hidden !important; }
        header { display: none !important; }
        .dashboard-card { background-color: white; border-radius: 10px; padding: 20px; margin-bottom: 20px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
        h1, h2, h3 { color: #1E88E5; }
        section[data-testid="stSidebar"] { background-color: #f8f9fa; }
        section[data-testid="stSidebar"] button { width: 100%; border-radius: 5px; text-align: left; margin-bottom: 5px; height: 40px; padding: 0 15px; font-size: 14px; }
        .active-button button { background-color: #e3f2fd !important; border-left: 3px solid #1E88E5 !important; color: #1E88E5 !important; font-weight: 500 !important; }
        section[data-testid="stSidebar"] > div:first-child { padding-top: 0; }
        .user-profile { background-color: white; padding: 10px; border-radius: 5px; margin-bottom: 15px; border: 1px solid #e0e0e0; }
        .sidebar-footer { position: fixed; bottom: 0; left: 0; width: 100%; background-color: #f8f9fa; border-top: 1px solid #e0e0e0; padding: 10px; font-size: 12px; color: #666; text-align: center; }
    </style>
    """, unsafe_allow_html=True)

    st.title("📊 Portal de Indicadores")

    if os.path.exists("logo.png"):
        st.sidebar.markdown(f"<div style='text-align: center;'>{img_to_html('logo.png')}</div>", unsafe_allow_html=True)
    else:
        st.sidebar.markdown("<h1 style='text-align: center; font-size: 40px;'>📊</h1>", unsafe_allow_html=True)

    st.sidebar.markdown("<hr style='margin: 15px 0;'>", unsafe_allow_html=True)

    with st.sidebar.container():
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown(f"""
            <div style="background-color: white; padding: 10px; border-radius: 5px; margin-bottom: 15px; border: 1px solid #e0e0e0;">
                <p style="margin:0; font-weight:bold;">{st.session_state.username}</p>
                <p style="margin:0; font-size:12px; color:#666;">{st.session_state.user_type}</p>
                {'<p style="margin:0; font-size:12px; color:#666;">Setor: ' + st.session_state.user_sector + '</p>' if st.session_state.user_type == "Operador" else ''}
            </div>
            """, unsafe_allow_html=True)
        with col2:
            if st.button("🚪", help="Fazer logout"):
                logout()

    if 'page' not in st.session_state:
        st.session_state.page = "Dashboard"

    if user_type == "Administrador":
        menu_items = ["Dashboard", "Criar Indicador", "Editar Indicador", "Preencher Indicador", "Visão Geral", "Configurações", "Gerenciar Usuários"]
    elif user_type == "Operador":
        menu_items = ["Dashboard", "Preencher Indicador", "Visão Geral"]
        if st.session_state.page not in menu_items: st.session_state.page = "Dashboard"
    else:
        menu_items = ["Dashboard", "Visão Geral"]
        if st.session_state.page not in menu_items: st.session_state.page = "Dashboard"

    for item in menu_items:
        icon = MENU_ICONS.get(item, "📋")
        is_active = st.session_state.page == item
        active_class = "active-button" if is_active else ""
        st.sidebar.markdown(f'<div class="{active_class}">', unsafe_allow_html=True)
        if st.sidebar.button(f"{icon} {item}", key=f"menu_{item}"):
            st.session_state.page = item
            st.rerun()
        st.sidebar.markdown('</div>', unsafe_allow_html=True)

    st.sidebar.markdown("""
    <div class="sidebar-footer">
        <p style="margin:0;">Portal de Indicadores v1.2</p>
        <p style="margin:3px 0 0 0;">© 2025 Todos os direitos reservados</p>
    </div>
    """, unsafe_allow_html=True)

    if st.session_state.page == "Dashboard":
        show_dashboard(SETORES, TEMA_PADRAO)
    elif st.session_state.page == "Criar Indicador" and user_type == "Administrador":
        create_indicator(SETORES, TIPOS_GRAFICOS)
    elif st.session_state.page == "Editar Indicador" and user_type == "Administrador":
        edit_indicator(SETORES, TIPOS_GRAFICOS)
    elif st.session_state.page == "Preencher Indicador" and user_type in ["Administrador", "Operador"]:
        fill_indicator(SETORES, TEMA_PADRAO)
    elif st.session_state.page == "Visão Geral":
        show_overview()
    elif st.session_state.page == "Configurações" and user_type == "Administrador":
        show_settings()
    elif st.session_state.page == "Gerenciar Usuários" and user_type == "Administrador":
        show_user_management(SETORES)
    else:
        st.warning("Você não tem permissão para acessar esta página.")
        st.session_state.page = "Dashboard"
        st.rerun()

    backup_thread = threading.Thread(target=agendar_backup, args=(cipher,))
    backup_thread.daemon = True
    backup_thread.start()

if __name__ == "__main__":
    main()
