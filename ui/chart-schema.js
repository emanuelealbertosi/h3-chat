export function validateChart(spec) {
  if (!spec || typeof spec !== 'object' || !['line','bar','scatter','pie','doughnut'].includes(spec.type)) throw Error('Tipo di grafico non supportato.');
  if (!Array.isArray(spec.datasets) || !spec.datasets.length || spec.datasets.length > 12) throw Error('Il grafico richiede da 1 a 12 serie.');
  const labels = spec.labels ?? [];
  if (!Array.isArray(labels) || labels.length > 2000 || labels.some(x => !['string','number'].includes(typeof x))) throw Error('Etichette non valide.');
  const datasets = spec.datasets.map(series => {
    if (!Array.isArray(series.data) || series.data.length > 2000) throw Error('Serie troppo grande o non valida.');
    const data = series.data.map(point => {
      if(spec.type === 'scatter') {
        if(!point || !Number.isFinite(point.x) || !Number.isFinite(point.y)) throw Error('Coordinate non valide.');
        return {x:point.x,y:point.y};
      }
      if(point !== null && !Number.isFinite(point)) throw Error('Il grafico richiede valori numerici finiti.');
      if(['pie','doughnut'].includes(spec.type) && (point === null || point < 0)) throw Error('Le sezioni devono essere numeri positivi.');
      return point;
    });
    if(spec.type !== 'scatter' && data.length !== labels.length) throw Error('Il numero di dati e di etichette deve coincidere.');
    return {label:String(series.label || 'Serie').slice(0,200),data};
  });
  return {type:spec.type,title:String(spec.title||'Grafico').slice(0,250),xLabel:String(spec.xLabel||'').slice(0,100),yLabel:String(spec.yLabel||'').slice(0,100),labels:labels.map(String),datasets};
}
