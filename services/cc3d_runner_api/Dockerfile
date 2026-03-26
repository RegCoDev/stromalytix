FROM continuumio/miniconda3:latest

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

RUN conda create -n cc3d -c compucell3d -c conda-forge compucell3d python=3.10 -y \
    && conda clean -afy

SHELL ["conda", "run", "-n", "cc3d", "/bin/bash", "-c"]

RUN pip install --no-cache-dir fastapi uvicorn httpx

WORKDIR /app
COPY main.py runner.py ./

ENV CC3D_PYTHON=/opt/conda/envs/cc3d/bin/python
ENV STROMALYTIX_API_KEY=change-me-in-production

EXPOSE 8001

CMD ["conda", "run", "--no-capture-output", "-n", "cc3d", \
     "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]