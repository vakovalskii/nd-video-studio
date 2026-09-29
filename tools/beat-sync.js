// beat-sync.js: sync HyperFrames animation to a track's real beat (beats.json from scripts/beat_map.py).
// Include in the composition and inline beats.json into the page (no fetch at render time):
//   <script>window.BEATS = {...beats.json contents...}</script>
//   <script src="beat-sync.js"></script>
//
// Ideas from rocketmandrey/vibecoder-anthem: cuts and hits on real beats, not a BPM grid;
// moving finished animation onto a new track version via piecewise-linear time warp.
(function () {
  const B = window.BEATS || { beats: [], downbeats: [], hits: [] };

  function nearest(arr, t) {
    let lo = 0, hi = arr.length - 1;
    if (hi < 0) return t;
    while (hi - lo > 1) { const m = (lo + hi) >> 1; if (arr[m] <= t) lo = m; else hi = m; }
    return Math.abs(arr[lo] - t) <= Math.abs(arr[hi] - t) ? arr[lo] : arr[hi];
  }
  function nextOf(arr, t) { for (const x of arr) if (x >= t - 1e-3) return x; return t; }

  window.beat = {
    data: B,
    // nearest beat / downbeat to a rough time: gsap.to(el, {...}, beat.snap(12.3))
    snap: (t) => nearest(B.beats, t),
    snapBar: (t) => nearest(B.downbeats, t),
    // first beat at or after t: cut "on the next beat"
    next: (t) => nextOf(B.beats, t),
    nextBar: (t) => nextOf(B.downbeats, t),
    // hits above threshold in a window: drive camera shake and flashes
    hits: (from, to, min = 6) => B.hits.filter(([t, s]) => t >= from && t < to && s >= min).map(([t]) => t),
    // beats in a window: pulse an element on each beat
    between: (from, to) => B.beats.filter((t) => t >= from && t < to),
  };

  // Time warp: animation was built for the old track version, audio is new. Anchors [new time, old time]
  // are placed on the same events in both versions (line starts, hits, downbeats), linear
  // in between. Two anchors with nearly equal new times = a hard cut in old time.
  // Usage: when building the timeline, tl.add(tween, warp(oldTime)) doesn't work (needs the inverse),
  // so the warp gives the position: tl.add(tween, beat.warpFrom(ANCHORS)(oldTime)).
  window.beat.warpFrom = function (anchors) {
    const A = anchors.slice().sort((a, b) => a[1] - b[1]);
    return function (oldT) {
      if (oldT <= A[0][1]) return A[0][0] + (oldT - A[0][1]);
      for (let i = 1; i < A.length; i++) {
        const [n0, o0] = A[i - 1], [n1, o1] = A[i];
        if (oldT <= o1) return o1 === o0 ? n1 : n0 + (oldT - o0) * (n1 - n0) / (o1 - o0);
      }
      const [nl, ol] = A[A.length - 1];
      return nl + (oldT - ol);
    };
  };
})();
