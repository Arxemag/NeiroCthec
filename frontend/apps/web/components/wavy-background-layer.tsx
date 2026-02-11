import { WavyBackground } from './ui/wavy-background';

export function WavyBackgroundLayer() {
  return (
    <div
      className="fixed inset-0 z-0 overflow-hidden bg-gradient-to-br from-[#e9e5ff] via-[#f5f3ff] to-[#fefce8]"
      aria-hidden
    >
      <WavyBackground
        containerClassName="absolute inset-0"
        colors={['#7A6CFF', '#9d93ff', '#c4b8ff', '#F5C542', '#7A6CFF']}
        backgroundFill="#e9e5ff"
        waveOpacity={0.78}
        blur={5}
        speed="slow"
        waveWidth={50}
      />
    </div>
  );
}
