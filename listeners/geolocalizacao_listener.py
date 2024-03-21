import asyncio, json, os
import logging
from aio_pika import IncomingMessage

from dto.paciente import PacienteCoordenadasTask, PacienteInterpolacaoTask
from integrations.datasaude_api import geolocalizacao_salvar
from listeners.config import inicialize, send_rabbitmq

from dotenv import load_dotenv

from listeners.paciente_listener import send_deadletter

load_dotenv()


_datasaude_api = os.environ.get('DATASAUDE_API')

log = logging.getLogger(__name__)

async def on_message(message: IncomingMessage):
    payload = None
    try:
        log.info("Processamento mensagem {}".format(message.body))
        body = message.body.decode("utf-8")
        payload = json.loads(body)
        paciente = PacienteCoordenadasTask(**payload)
        result = await geolocalizacao_salvar(paciente.id)
        if (result.status_code != 200):
            await send_deadletter(payload, result.content)

        contents_json = json.loads(result.content.decode('utf-8'))
        for content in contents_json:
            paciente_interpolacao_task = PacienteInterpolacaoTask(id=str(content['id']))
            await send_rabbitmq(paciente_interpolacao_task.to_message(), "interpolacao_insert")

        log.info(f"Fim mensagem {message.body} - resultado {result}")
        await message.ack()
    except Exception as e:
        log.error(f"Erro no processamento da mensagem: {e}")
        await send_deadletter (payload, str(e))
        await message.ack()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(inicialize(loop, "geolocalizacao_upsert", on_message))
    loop.run_forever()
