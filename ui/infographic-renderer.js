import '../static/infographic-motion.js';
import renderMath from 'katex/contrib/auto-render';
import {readableText} from './slide-html-contrast.js';
import {fitMediaBounds} from './slide-html-bounds.js';

// The offline renderer uses the same trusted repairs as the editable canvas.
globalThis.H3Infographic={prepare(doc,height){
 H3Motion.freeze(doc);
 renderMath(doc.body,{delimiters:[{left:'$$',right:'$$',display:true},{left:'$',right:'$',display:false}],throwOnError:false});
 readableText(doc);fitMediaBounds(doc,height);
}};
