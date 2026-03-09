"""
Патч для Coqui XTTS: выравнивание длины position_ids и inputs_embeds в GPT2.

Исправляет RuntimeError: The size of tensor a (44) must match the size of tensor b (42)
в transformers/models/gpt2/modeling_gpt2.py (hidden_states = inputs_embeds + position_embeds).

Причина: при pad_token_id == eos_token_id HuggingFace generate() может передавать
attention_mask короче, чем input_ids; position_ids тогда получают длину 42, а emb — 44.
Патч перед вызовом transformer явно задаёт position_ids по длине emb.
"""
from __future__ import annotations

import logging

logger = logging.getLogger("tts-xtts")


def apply_xtts_position_embeddings_patch() -> None:
    try:
        import torch
        from TTS.tts.layers.xtts import gpt_inference

        _original_forward = gpt_inference.GPT2InferenceModel.forward

        def _patched_forward(
            self,
            input_ids=None,
            past_key_values=None,
            attention_mask=None,
            token_type_ids=None,
            position_ids=None,
            head_mask=None,
            inputs_embeds=None,
            encoder_hidden_states=None,
            encoder_attention_mask=None,
            labels=None,
            use_cache=None,
            output_attentions=None,
            output_hidden_states=None,
            return_dict=None,
        ):
            # Вызовем оригинал — он построит emb и передаст его в transformer.
            # Мы не можем поправить position_ids до вызова, т.к. emb создаётся внутри forward.
            # Поэтому оборачиваем вызов self.transformer внутри оригинального forward —
            # нет, мы не имеем доступа. Значит патчим так: перехватываем результат вызова
            # оригинального forward... но тогда мы не можем изменить аргументы.
            # Правильный способ: патчить именно то место, где вызывается self.transformer,
            # т.е. подменить метод forward так, чтобы он сам строил emb, затем исправлял
            # position_ids по emb.shape[1], и вызывал self.transformer с исправленным position_ids.
            # Для этого нужно повторить логику forward (или вызвать оригинал с подменённым position_ids).
            # В оригинале position_ids передаётся в self.transformer(...). Мы не можем изменить
            # position_ids до вызова оригинального forward, т.к. emb строится внутри него.
            # Единственный вариант: полностью переписать forward в патче, скопировав код из
            # gpt_inference.py и вставив исправление. Это хрупко при обновлении TTS.
            # Альтернатива: патчить не GPT2InferenceModel, а self.transformer (GPT2Model).
            # Т.е. обернуть self.transformer.forward так, чтобы при inputs_embeds и position_ids
            # с разной длиной мы подставляли position_ids = arange(inputs_embeds.shape[1]).
            # Тогда патч один раз при загрузке — подменяем transformer.forward у уже созданного
            # gpt_inference. Но gpt_inference создаётся внутри TTS при загрузке модели, т.е. после
            # нашего импорта. Значит при первом вызове synthesize мы уже имеем модель с gpt_inference.
            # Мы не можем пропатчить класс до создания экземпляра: мы патчим GPT2InferenceModel.forward.
            # Внутри forward создаётся emb и вызывается self.transformer(..., position_ids=position_ids).
            # Если мы в патче делаем: вызываем _original_forward, но перед этим подменяем
            # self.transformer на обёртку, которая исправляет position_ids — то при вызове
            # _original_forward он вызовет self.transformer(...), и наша обёртка получит
            # inputs_embeds=emb и position_ids=... и сможет поправить. Но тогда нам нужно
            # подменять self.transformer на обёртку в каждом экземпляре, что делается после
            # создания модели. Т.е. в _load_xtts после TTS() мы бы делали что-то вроде
            # getattr(tts, 'synthesizer', None) or getattr(tts, 'tts_model', None) и т.д.,
            # чтобы добраться до gpt_inference и пропатчить его transformer. Сложно и зависит от API.
            #
            # Проще: в патче forward мы не вызываем оригинал целиком, а копируем его логику
            # и вставляем исправление position_ids перед self.transformer(...). Тогда при
            # обновлении TTS может понадобиться обновить патч. Берём код из gpt_inference.py v0.22.0.
            assert self.cached_prefix_emb is not None
            assert inputs_embeds is None
            assert labels is None
            return_dict = return_dict if return_dict is not None else self.config.use_return_dict

            prefix_len = self.cached_prefix_emb.shape[1]
            if input_ids.shape[1] != 1:
                gen_inputs = input_ids[:, prefix_len:]
                gen_emb = self.embeddings(gen_inputs)
                gen_emb = gen_emb + self.pos_embedding(gen_emb)
                if self.cached_prefix_emb.shape[0] != gen_emb.shape[0]:
                    prefix_emb = self.cached_prefix_emb.repeat_interleave(
                        gen_emb.shape[0] // self.cached_prefix_emb.shape[0], 0
                    )
                else:
                    prefix_emb = self.cached_prefix_emb.to(gen_emb.dtype)
                emb = torch.cat([prefix_emb, gen_emb], dim=1)
            else:
                emb = self.embeddings(input_ids)
                pos_ind = attention_mask.shape[1] - (prefix_len + 1)
                # LearnedPositionEmbeddings имеет ограниченный seq_len — индекс не должен выходить за границы
                pos_max = getattr(self.pos_embedding, "seq_len", 1024) - 1
                pos_ind = max(0, min(int(pos_ind), pos_max))
                emb = emb + self.pos_embedding.get_fixed_embedding(pos_ind, attention_mask.device)

            # Исправление: длина position_embeds в GPT2 должна совпадать с inputs_embeds (emb).
            seq_len = emb.shape[1]
            if position_ids is None or position_ids.shape[1] != seq_len:
                position_ids = torch.arange(
                    seq_len, device=emb.device, dtype=torch.long
                ).unsqueeze(0).expand(emb.shape[0], -1)

            transformer_outputs = self.transformer(
                inputs_embeds=emb,
                past_key_values=past_key_values,
                attention_mask=attention_mask,
                token_type_ids=token_type_ids,
                position_ids=position_ids,
                head_mask=head_mask,
                encoder_hidden_states=encoder_hidden_states,
                encoder_attention_mask=encoder_attention_mask,
                use_cache=use_cache,
                output_attentions=output_attentions,
                output_hidden_states=output_hidden_states,
                return_dict=return_dict,
            )
            from transformers.modeling_outputs import CausalLMOutputWithCrossAttentions

            hidden_states = transformer_outputs[0]
            lm_logits = self.lm_head(hidden_states)

            if not return_dict:
                return (lm_logits,) + transformer_outputs[1:]

            return CausalLMOutputWithCrossAttentions(
                loss=None,
                logits=lm_logits,
                past_key_values=transformer_outputs.past_key_values,
                hidden_states=transformer_outputs.hidden_states,
                attentions=transformer_outputs.attentions,
                cross_attentions=transformer_outputs.cross_attentions,
            )

        gpt_inference.GPT2InferenceModel.forward = _patched_forward
        logger.info("XTTS GPT2 position_ids patch applied (inputs_embeds vs position_embeds length fix)")
    except Exception as e:
        logger.warning("XTTS position_ids patch failed (will rely on stock TTS): %s", e)
