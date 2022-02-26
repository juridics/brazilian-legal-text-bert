import math
from datetime import datetime
from sentence_transformers import SentenceTransformer
from sentence_transformers import models, losses
from sentence_transformers.evaluation import BinaryClassificationEvaluator
from torch.utils.data import DataLoader

from tools import *


class SimcseTrain:
    def __init__(self, model_name_or_path, epoch):
        self.logger = AppLogger()
        self.downloader = Downloader()
        self.sampler = ExamplePreparer()
        self.model_name = model_name_or_path
        self.num_epochs = int(epoch)
        self.train_batch_size = 5
        self.max_seq_length = 256

    def train(self):
        train_dataloader = self.prepare_train_dataloader()
        dev_evaluator = self.prepare_evaluator('dev.csv')
        test_evaluator = self.prepare_evaluator('test.csv')
        model = self.prepare_model()
        # self.test_model_before_train(model, test_evaluator)
        saved_model = self.make_train(model, train_dataloader, dev_evaluator)
        self.test_model_after_train(saved_model, test_evaluator)

    def prepare_train_dataloader(self):
        corpus_path = 'resources/corpus'
        corpus_samples = self.sampler.prepare_mlm(corpus_path)
        corpus_dataloader = DataLoader(corpus_samples,
                                       shuffle=True,
                                       batch_size=self.train_batch_size,
                                       drop_last=True)
        return corpus_dataloader

    def prepare_evaluator(self, filename):
        filepath = f'resources/{filename}'
        samples = self.sampler.prepare_sts(filepath)
        evaluator = BinaryClassificationEvaluator.from_input_examples(samples,
                                                                      show_progress_bar=True,
                                                                      batch_size=self.train_batch_size,
                                                                      name=f'sts-{filename}')
        return evaluator

    def prepare_model(self):
        word_embedding_model = models.Transformer(self.model_name, max_seq_length=self.max_seq_length)
        pooling_model = models.Pooling(word_embedding_model.get_word_embedding_dimension())
        return SentenceTransformer(modules=[word_embedding_model, pooling_model])

    def make_train(self, model, corpus_dataloader, dev_evaluator):
        model_checkpoint_path = 'output/simcse_checkpoints'
        model_save_path = 'output/simcse-{}'.format(datetime.now().strftime("%Y-%m-%d_%H-%M-%S"))
        warmup_steps = math.ceil(len(corpus_dataloader) * self.num_epochs * 0.1)
        evaluation_steps = int(len(corpus_dataloader) * 0.25)
        train_loss = losses.MultipleNegativesRankingLoss(model)
        model.fit(train_objectives=[(corpus_dataloader, train_loss)],
                  evaluator=dev_evaluator,
                  epochs=self.num_epochs,
                  evaluation_steps=evaluation_steps,
                  warmup_steps=warmup_steps,
                  output_path=model_save_path,
                  optimizer_params={'lr': 5e-5},
                  save_best_model=True,
                  checkpoint_path=model_checkpoint_path,
                  checkpoint_save_steps=evaluation_steps,
                  use_amp=True
                  )
        return model_save_path

    @staticmethod
    def test_model_before_train(model, test_evaluator):
        test_evaluator(model)

    @staticmethod
    def test_model_after_train(model_saved_path, test_evaluator):
        saved_model = SentenceTransformer(model_saved_path)
        test_evaluator(saved_model, output_path=model_saved_path)


if __name__ == '__main__':
    model, epochs = parse_commands()
    trainner = SimcseTrain(model, epochs)
    trainner.train()
