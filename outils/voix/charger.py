#!/usr/bin/env python3
"""Charge le modele acoustique de Mmeslay, sans l'enveloppe Lightning. Les poids chargent ici appartiennent au projet Mmeslay (GPL-3.0) : https://github.com/G1ya777/Mmeslay_backend-CLI"""
import sys

import torch
from nemo.collections.asr.modules import AudioToMelSpectrogramPreprocessor, ConvASRDecoder
from nemo.collections.asr.modules.squeezeformer_encoder import SqueezeformerEncoder
from nemo.core import typecheck

typecheck.set_typecheck_enabled(False)


class Mmeslay(torch.nn.Module):
    """Le modele du depot Mmeslay : spectrogramme mel, encodeur, decodeur CTC."""

    def __init__(self):
        super().__init__()
        self.processor = AudioToMelSpectrogramPreprocessor(
            sample_rate=16000, features=80, n_fft=512,
            window_size=0.025, window_stride=0.01, log=True, frame_splicing=True)
        self.encoder = SqueezeformerEncoder(
            feat_in=80, feat_out=-1, n_layers=16, d_model=144,
            adaptive_scale=True, time_reduce_idx=7,
            dropout_emb=0, dropout_att=0.1, subsampling_factor=4)
        self.decoder = ConvASRDecoder(feat_in=144, num_classes=128)

    def forward(self, x, lengths):
        spec, l = self.processor(input_signal=x, length=lengths)
        enc = self.encoder(audio_signal=spec, length=l)
        return self.decoder(encoder_output=enc[0])


if __name__ == "__main__":
    m = Mmeslay()
    sd = torch.load(sys.argv[1], map_location="cpu")
    manquants, inattendus = m.load_state_dict(sd, strict=False)
    print("parametres attendus et absents :", len(manquants))
    print("parametres fournis et inutilises :", len(inattendus))
    for k in list(manquants)[:5]:
        print("    manque :", k)
    for k in list(inattendus)[:5]:
        print("    en trop :", k)
    m.eval()
    with torch.no_grad():
        y = m(torch.zeros(1, 16000), torch.tensor([16000]))
    print("sortie sur 1 s de silence :", tuple(y.shape))
