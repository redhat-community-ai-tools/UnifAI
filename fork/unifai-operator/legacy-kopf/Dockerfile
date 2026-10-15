FROM quay.io/fedora/python-312:latest
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY unifai_operator.py client.py ./
USER 1001
CMD ["kopf", "run", "--standalone", "unifai_operator.py"]
