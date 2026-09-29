// beat-sync.js: привязка анимации HyperFrames к реальному биту трека (beats.json из scripts/beat_map.py).
// Подключить в композицию и вставить beats.json прямо в страницу (fetch при рендере не нужен):
//   <script>window.BEATS = {...содержимое beats.json...}</script>
//   <script src="beat-sync.js"></script>
//
// Идеи из rocketmandrey/vibecoder-anthem: склейки и удары на реальные доли, а не на сетку по BPM;
// перенос готовой анимации на новую версию трека через кусочно-линейный тайм-варп.
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
    // ближайшая доля / сильная доля к черновому времени: gsap.to(el, {...}, beat.snap(12.3))
    snap: (t) => nearest(B.beats, t),
    snapBar: (t) => nearest(B.downbeats, t),
    // первая доля не раньше t: склейка «на следующий бит»
    next: (t) => nextOf(B.beats, t),
    nextBar: (t) => nextOf(B.downbeats, t),
    // удары сильнее порога в окне: по ним трясти камеру и вспышки
    hits: (from, to, min = 6) => B.hits.filter(([t, s]) => t >= from && t < to && s >= min).map(([t]) => t),
    // доли в окне: пульс элемента на каждую долю
    between: (from, to) => B.beats.filter((t) => t >= from && t < to),
  };

  // Тайм-варп: анимация свёрстана под старую версию трека, звук новый. Якоря [новое время, старое время]
  // ставятся на одни и те же события обеих версий (начала строк, удары, сильные доли), между ними
  // линейно. Два якоря с почти одинаковым новым временем = жёсткая склейка в старом времени.
  // Применение: при сборке таймлайна tl.add(tween, warp(oldTime)) не работает (нужно обратное),
  // поэтому варп задаёт позицию: tl.add(tween, beat.warpFrom(ANCHORS)(oldTime)).
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
