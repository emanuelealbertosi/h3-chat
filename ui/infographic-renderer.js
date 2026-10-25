import '../static/infographic-motion.js';
import renderMath from 'katex/contrib/auto-render';
import {readableText} from './slide-html-contrast.js';
import {fitMediaBounds} from './slide-html-bounds.js';
import {portraitLayout} from './infographic-layout.js';
import {applyHtmlBackground} from './slide-background-style.js';

// The offline renderer uses the same trusted repairs as the editable canvas.
globalThis.H3Infographic={measure:portraitLayout,async prepare(doc,height,options={},duration=30){
 H3Motion.screen(doc,options,duration);
 const specification=doc.querySelector('[data-h3-background-spec]');
 if(specification){const spec=JSON.parse(specification.textContent);specification.remove();await applyHtmlBackground(doc,spec.deck,spec.page,spec.media,height);H3Motion.screen(doc,options,duration);await Promise.all([...doc.images].map(image=>image.decode().catch(()=>{})));}
 H3Motion.freeze(doc);
 renderMath(doc.body,{delimiters:[{left:'$$',right:'$$',display:true},{left:'$',right:'$',display:false}],throwOnError:false});
 readableText(doc);fitMediaBounds(doc,height);
 H3Motion.configure(doc,options);
}};
