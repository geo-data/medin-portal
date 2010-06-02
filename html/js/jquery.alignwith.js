/**
 * jQuery alignWith plug-in v0.1
 * Align two or more elements with each other
 *
 * @requires jQuery v1.2 or later
 *
 * Copyright (c) 2009 Gilmore Davidson
 *
 * Licensed under the MIT license:
 *   http://www.opensource.org/licenses/mit-license.php
 */
(function($){$.fn.extend({alignWith:function(elem,pos,options){elem=$(elem);var eDom=elem.get(0),eOff=elem.offset(),eX=eOff.left,eY=eOff.top,eW=eDom.offsetWidth,eH=eDom.offsetHeight,pT='',pE='',args=[],rXM=/^([tbcm]{2}|lr|rl)$/i,rXR=/^r?[rtbcm]r?$/i,rYM=/^([lrcm]{2}|tb|bt)$/i,rYB=/^b?[lrbcm]b?$/i,tCss={position:'absolute',left:eX,top:eY},op={x:0,y:0,appendToBody:false};if(undefined!==options){$.extend(op,options);} if(!/^[tblrcm]{1,4}$/.test(pos)){pos='c';} args=pos.split('');switch(args.length){case 1:pT=pE=''+pos+pos;break;case 2:pT=pE=pos;break;case 3:pT=''+args[0]+args[1];pE=''+args[2]+args[2];break;case 4:pT=''+args[0]+args[1];pE=''+args[2]+args[3];break;} return this.each(function(){var t=$(this),tX=eX,tY=eY,tW=this.offsetWidth,tH=this.offsetHeight;if(rXM.test(pT)){tX-=(tW/2);}else if(rXR.test(pT)){tX-=tW;} if(rXM.test(pE)){tX+=(eW/2);}else if(rXR.test(pE)){tX+=eW;} if(rYM.test(pT)){tY-=(tH/2);}else if(rYB.test(pT)){tY-=tH;} if(rYM.test(pE)){tY+=(eH/2);}else if(rYB.test(pE)){tY+=eH;} tX-=parseInt(t.css('margin-left'),10);tY-=parseInt(t.css('margin-top'),10);if(0!==op.x){tX+=parseInt(op.x,10);} if(0!==op.y){tY+=parseInt(op.y,10);} tCss.left=tX;tCss.top=tY;t.css(tCss);if(op.appendToBody){t.appendTo('body');}});}});})(jQuery);