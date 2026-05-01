<?php

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

class SemanticRatingHtmlRenderer {

	private $imagepath = null;

	public function __construct( $imagepath ) {
		$this->imagepath = $imagepath;
	}

	private function render( $parser, $params ) {

		if ( count( $params ) > 1 ) {
			$rating = $params[1];
			if ( !is_numeric( $rating ) ) {
				$rating = 0;
			}
		} else {
			$rating = 0;
		}
		if ( count( $params ) > 2 ) {
			$max = $params[2];
		} else {
			$max = $GLOBALS['wgSemanticRating_DefaultMax'];
		}

		$output = Html::openElement( 'span', array(
			'style' => 'white-space:nowrap;'
		) );

		if ( $rating < 0 ) {
			$rating = 0;
		} elseif ( $rating > $max ) {
			$rating = $max;
		}

		$i = 1;
		while ( $i <= $rating ) {
			$output .=
				Html::element( 'img',
					array( 'src' => $this->imagepath . 'yellowstar.png' ) );
			$i++;
		}
		if ( $rating - $i + 1 != 0 ) {
			$output .=
				Html::element( 'img',
					array( 'src' => $this->imagepath . 'halfstar.png' ) );
			$i++;
		}
		while ( $i <= $max ) {
			$output .=
				Html::element( 'img',
					array( 'src' => $this->imagepath . 'greystar.png' ) );
			$i++;
		}

		$output .= Html::closeElement( 'span' );

		return $output;

	}

	public function renderInline( $parser, $params ) {
		$output = $this->render( $parser, $params );
		return array( $parser->insertStripItem( $output ),
			'noparse' => false, 'isHTML' => true );
	}

	public function renderBeforeTitle( $parser, $params ) {
		$out = $parser->getOutput();
		$rating = $this->render( $parser, $params ) . "&nbsp;";
		$out->addJsConfigVars( 'SemanticRatingBefore', $rating );
		$cssSelector = $GLOBALS['wgSemanticRating_CSSSelector'];
		$out->addJsConfigVars( 'SemanticRatingSelector', $cssSelector );
		$out->addModules( 'ext.SemanticRating' );
		return "";
	}

	public function renderAfterTitle( $parser, $params ) {
		$out = $parser->getOutput();
		$rating = "&nbsp;" . $this->render( $parser, $params );
		$out->addJsConfigVars( 'SemanticRatingAfter', $rating );
		$cssSelector = $GLOBALS['wgSemanticRating_CSSSelector'];
		$out->addJsConfigVars( 'SemanticRatingSelector', $cssSelector );
		$out->addModules( 'ext.SemanticRating' );
		return "";
	}
}
