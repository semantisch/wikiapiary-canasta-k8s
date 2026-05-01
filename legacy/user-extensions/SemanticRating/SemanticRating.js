/*
 * Copyright (c) 2014-2016 The MITRE Corporation
 *
 * Permission is hereby granted, free of charge, to any person obtaining a
 * copy of this software and associated documentation files (the "Software"),
 * to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense,
 * and/or sell copies of the Software, and to permit persons to whom the
 * Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in
 * all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
 * FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
 * DEALINGS IN THE SOFTWARE.
 */

var semanticRating = ( function ( $ ) {

	'use strict';

	return {
		setrating: function ( rating, inputId, max ) {
			$( '#' + inputId )
				.attr( 'value', rating );
			var i = 1,
				star,
				src;
			while ( i <= rating ) {
				star = $( '#' + inputId + '_s_' + i );
				src = star.attr( 'src' );
				src = src.replace( 'grey', 'yellow' );
				star.attr( 'src', src );
				i++;
			}
			while ( i <= max ) {
				star = $( '#' + inputId + '_s_' + i );
				src = star.attr( 'src' );
				src = src.replace( 'yellow', 'grey' );
				star.attr( 'src', src );
				i++;
			}
		}
	};
}( jQuery ) );

window.semanticRating = semanticRating;

$( function () {
	if ( mw.config.exists( 'SemanticRatingSelector' ) ) {
		var selector = mw.config.get( 'SemanticRatingSelector' );
		if ( mw.config.exists( 'SemanticRatingBefore' ) ) {
			var before = mw.config.get( 'SemanticRatingBefore' );
			jQuery( selector ).each( function ( index ) {
				jQuery( this ).prepend( before );
			} );
		}
		if ( mw.config.exists( 'SemanticRatingAfter' ) ) {
			var after = mw.config.get( 'SemanticRatingAfter' );
			jQuery( selector ).each( function ( index ) {
				jQuery( this ).append( after );
			} );
		}
	}
} );
