'use client';

import { useState, useEffect } from 'react';
import { VoiceMetadata, getAllVoices, getVoiceAudioUrl } from '@/lib/voice-cache';

/**
 * Компонент для предпросмотра голосов актеров
 */
export function VoicePreview({ voiceId }: { voiceId: string }) {
  const [voice, setVoice] = useState<VoiceMetadata | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [audio, setAudio] = useState<HTMLAudioElement | null>(null);

  useEffect(() => {
    async function loadVoice() {
      const data = await getAllVoices();
      const found = data.find((v) => v.id === voiceId);
      setVoice(found || null);
    }
    loadVoice();
  }, [voiceId]);

  const handlePlay = () => {
    if (!voice) return;

    if (audio) {
      audio.pause();
      audio.currentTime = 0;
    }

    const audioUrl = getVoiceAudioUrl(voice.audioFile);
    const newAudio = new Audio(audioUrl);
    
    newAudio.onended = () => setIsPlaying(false);
    newAudio.onerror = () => {
      console.error('Failed to load audio:', audioUrl);
      setIsPlaying(false);
    };

    newAudio.play();
    setAudio(newAudio);
    setIsPlaying(true);
  };

  const handleStop = () => {
    if (audio) {
      audio.pause();
      audio.currentTime = 0;
      setIsPlaying(false);
    }
  };

  if (!voice) {
    return <div>Голос не найден</div>;
  }

  return (
    <div className="voice-preview p-4 border rounded-lg">
      <h3 className="text-lg font-semibold mb-2">{voice.name}</h3>
      <p className="text-sm text-gray-600 mb-2">{voice.description}</p>
      <p className="text-sm mb-4 italic">"{voice.previewText}"</p>
      
      <div className="flex gap-2 items-center">
        <button
          onClick={isPlaying ? handleStop : handlePlay}
          className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
        >
          {isPlaying ? '⏸ Остановить' : '▶ Воспроизвести'}
        </button>
        
        <div className="flex gap-2">
          <span className="text-xs px-2 py-1 bg-gray-100 rounded">
            {voice.gender === 'male' ? '👨 Мужской' : '👩 Женский'}
          </span>
          <span className="text-xs px-2 py-1 bg-gray-100 rounded">
            {voice.language.toUpperCase()}
          </span>
        </div>
      </div>

      {voice.tags.length > 0 && (
        <div className="mt-2 flex gap-1 flex-wrap">
          {voice.tags.map((tag) => (
            <span key={tag} className="text-xs px-2 py-1 bg-blue-100 text-blue-800 rounded">
              {tag}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

/**
 * Компонент для списка всех голосов
 */
export function VoiceList() {
  const [voices, setVoices] = useState<VoiceMetadata[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadVoices() {
      const data = await getAllVoices();
      setVoices(data);
      setLoading(false);
    }
    loadVoices();
  }, []);

  if (loading) {
    return <div>Загрузка голосов...</div>;
  }

  if (voices.length === 0) {
    return <div>Голосы не найдены. Добавьте их в папку cache/voices/</div>;
  }

  return (
    <div className="voice-list grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {voices.map((voice) => (
        <VoicePreview key={voice.id} voiceId={voice.id} />
      ))}
    </div>
  );
}
