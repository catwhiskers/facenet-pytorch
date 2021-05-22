ARG BASE_IMG=${BASE_IMG}
FROM ${BASE_IMG} 
RUN git clone https://github.com/catwhiskers/facenet-pytorch.git
RUN cp changehostname.c /facenet-pytorch/
RUN cd /facenet-pytorch && python setup.py install && pip install tensorboard==1.15  
WORKDIR /facenet-pytorch
ENV PATH="/facenet-pytorch:${PATH}"
ENTRYPOINT ["python", "train.py"]
