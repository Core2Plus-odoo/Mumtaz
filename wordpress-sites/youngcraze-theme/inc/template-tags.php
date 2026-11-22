<?php
/**
 * Custom template tags for Young Craze.
 */
if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

if ( ! function_exists( 'yc_posted_on' ) ) {
	function yc_posted_on() {
		$time_string = '<time class="entry-date published" datetime="%1$s">%2$s</time>';
		$time_string = sprintf(
			$time_string,
			esc_attr( get_the_date( DATE_W3C ) ),
			esc_html( get_the_date() )
		);
		echo $time_string; // phpcs:ignore WordPress.Security.EscapeOutput.OutputNotEscaped -- built from esc_* calls above.
	}
}

if ( ! function_exists( 'yc_posted_by' ) ) {
	function yc_posted_by() {
		printf(
			/* translators: %s: author display name */
			esc_html__( 'by %s', 'youngcraze' ),
			'<span class="author vcard">' . esc_html( get_the_author() ) . '</span>'
		);
	}
}

if ( ! function_exists( 'yc_pagination' ) ) {
	function yc_pagination() {
		the_posts_pagination( array(
			'mid_size'  => 1,
			'prev_text' => __( '&larr; Older', 'youngcraze' ),
			'next_text' => __( 'Newer &rarr;', 'youngcraze' ),
			'class'     => 'pagination',
		) );
	}
}
