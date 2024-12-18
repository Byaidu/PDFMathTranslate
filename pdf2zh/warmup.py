from doclayout import DocLayoutModel

def warmup():
    print('Warming up the model...')
    DocLayoutModel.load_available()
    print('Warm-up completed!')


if __name__ == "__main__":
    warmup()