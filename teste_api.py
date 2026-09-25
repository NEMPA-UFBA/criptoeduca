from fastapi import FastAPI

app = FastAPI()

@app.get("/status")
def checar_status():
    return {"mensagem": "O servidor Python do CriptoEduca esta rodando!"}
