import logging
import os
import uvicorn
from fastapi import FastAPI
from vital_agent_container.agent_container_app import AgentContainerApp
from vital_ai_vitalsigns.vitalsigns import VitalSigns
from slxx_agent.agent.agent_impl import AgentImpl
from slxx_agent.slxx_message_handler import slxxMessageHandler
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)


def create_app():

    logger = logging.getLogger(__name__)

    logger.info('Hello slxx Agent')

    vs = VitalSigns()

    logger.info(f"VitalSigns Initialized.")

    current_file_directory = os.path.dirname(os.path.abspath(__file__))

    app_home = current_file_directory

    agent = AgentImpl()

    handler = slxxMessageHandler(agent=agent, app_home=app_home)

    # Create a FastAPI app
    fastapi_app = FastAPI()

    # Add health check route
    @fastapi_app.get("/health")
    async def health_check():
        """
        Health check endpoint to verify the application is running.
        Returns a simple status message.
        """
        return {
            "status": "healthy",
            "message": "slxx RequestHandler Agent is up and running"
        }

    # Wrap the AgentContainerApp with FastAPI
    container_app = AgentContainerApp(handler, app_home)
    
    # Mount the container app's routes
    fastapi_app.mount("/", container_app)

    return fastapi_app


app = create_app()


if __name__ == "__main__":
    uvicorn.run(host="0.0.0.0", port=7009, app=app)

