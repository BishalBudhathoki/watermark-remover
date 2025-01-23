import React, { useEffect, useRef } from 'react';

const LoadingAnimation = () => {
  const containerRef = useRef(null);
  const animationRef = useRef(null);

  useEffect(() => {
    if (typeof window.bodymovin !== 'undefined') {
      // Load and play the animation
      animationRef.current = window.bodymovin.loadAnimation({
        container: containerRef.current,
        renderer: 'svg',
        loop: true,
        autoplay: true,
        path: '/assets/loading.lottie' // Adjust path as needed
      });
    }

    // Cleanup on unmount
    return () => {
      if (animationRef.current) {
        animationRef.current.destroy();
      }
    };
  }, []);

  return (
    <div className="flex flex-col items-center justify-center p-8">
      <div 
        ref={containerRef} 
        className="w-32 h-32"
        aria-label="Loading animation"
      />
      <p className="mt-4 text-gray-600 text-sm">Loading your content...</p>
    </div>
  );
};

export default LoadingAnimation;