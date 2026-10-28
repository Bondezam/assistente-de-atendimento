import os
import sqlite3
import time
import pandas as pd
import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader
import streamlit as st
from dotenv import load_dotenv
from openai import AzureOpenAI, APIError


load_dotenv(override=True)


client = AzureOpenAI(
    azure_endpoint=os.getenv("ENDPOINT"),
    api_key=os.getenv("API_KEY"),
    api_version=os.getenv("API_VERSION", "2025-04-01-preview")
)
deployment_name = os.getenv("GPT5_MODEL")


@st.cache_data
def raspar_site():
    url = "https://gratuitos.netlify.app/"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        for script in soup(["script", "style"]):
            script.extract()
        texto = soup.get_text(separator="\n", strip=True)
        # Limita o texto do site aos primeiros 3000 caracteres para poupar tokens
        return texto[:3000]
    except Exception as e:
        return f"Erro ao acessar o site: {e}"


@st.cache_data
def ler_pdf():
    caminho_pdf = "arquivo.pdf"
    if not os.path.exists(caminho_pdf):
        return "Arquivo PDF não encontrado."
    try:
        reader = PdfReader(caminho_pdf)
        texto = ""
        for page in reader.pages:
            texto += page.extract_text() or ""
        # Limita o texto do PDF aos primeiros 3000 caracteres
        return texto[:3000]
    except Exception as e:
        return f"Erro ao ler o PDF: {e}"


def carregar_dados_locais():
    try:
        dados_csv = pd.read_csv('dados.csv').head(50).to_string()
    except Exception:
        dados_csv = "dados.csv não encontrado."


    try:
        t_csv = pd.read_csv('tic.csv').head(50).to_string()
    except Exception:
        t_csv = "tic.csv não encontrado."


    try:
        con = sqlite3.connect('banco.db')
        cursor = con.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS vendas(
                         venda REAL,
                         vendedor TEXT,
                         id TEXT)''')
        con.commit()
        cursor.execute('SELECT * FROM vendas')
        dados_db = str(cursor.fetchall())
        con.close()
    except Exception:
        dados_db = "Banco de dados vazio ou não encontrado."


    return dados_csv, t_csv, dados_db


def main():
    st.set_page_config(page_title="Assistente de Atendimento", page_icon="🤖", layout="centered")


    st.title("🤖 Assistente Virtual Unificado")
    st.write("Consulte informações institucionais, dados de vendas, CSVs e documentos em um só lugar.")


    # Carrega as bases com limite de segurança para tokens
    dados_csv, t_csv, dados_db = carregar_dados_locais()
    conteudo_site = raspar_site()
    conteudo_pdf = ler_pdf()


    # Prompt unificado e compacto
    prompt_sistema = f"""
Você é um assistente de atendimento inteligente. Responda à dúvida do usuário utilizando EXCLUSIVAMENTE os contextos abaixo:


----[DADOS DO SITE]----
{conteudo_site}


----[CONTEÚDO DO PDF]----
{conteudo_pdf}


----[DADOS DO CSV 1]----
{dados_csv}


----[DADOS DO CSV 2]----
{t_csv}


----[BANCO DE DADOS DE VENDAS]----
{dados_db}
"""


    pergunta = st.text_input("Digite sua dúvida, endereço, vendedor ou dado desejado:")


    if st.button("Buscar / Perguntar"):
        if not pergunta.strip():
            st.warning("Por favor, digite uma pergunta válida.")
            return


        if not os.getenv("ENDPOINT") or not os.getenv("API_KEY") or not deployment_name:
            st.error("Erro de configuração: Variáveis de ambiente da Azure ausentes.")
            return


        max_tentativas = 3
        for tentativa in range(max_tentativas):
            try:
                with st.spinner(f"Consultando bases unificadas e gerando resposta..."):
                    response = client.chat.completions.create(
                        model=deployment_name,
                        messages=[
                            {"role": "system", "content": prompt_sistema},
                            {"role": "user", "content": pergunta}
                        ],
                        # max_tokens=1200
                    )
                    resposta_texto = response.choices[0].message.content
                    st.markdown("### Resposta:")
                    st.success(resposta_texto)
                    break
            except APIError as e:
                if getattr(e, 'status_code', None) == 429 or "429" in str(e):
                    if tentativa < max_tentativas - 1:
                        time.sleep(5)
                    else:
                        st.error("O limite de tokens da API foi atingido. Tente novamente em instantes.")
                else:
                    st.error(f"Erro na API Azure: {e}")
                    break
            except Exception as e:
                st.error(f"Erro inesperado: {e}")
                break


if __name__ == "__main__":
    main()