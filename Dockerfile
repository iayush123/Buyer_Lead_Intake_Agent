FROM python:3.11-slim

WORKDIR /app

# System deps kept minimal; psycopg[binary] ships its own libpq.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8501

# Railway injects $PORT at runtime; fall back to 8501 for local Docker runs.
CMD ["sh", "-c", "streamlit run streamlit_app.py --server.port ${PORT:-8501} --server.address 0.0.0.0 --server.headless true"]
