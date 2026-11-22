<?php
/**
 * Custom template tags for Oddity Trend.
 */
if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

if ( ! function_exists( 'ot_posted_on' ) ) {
	function ot_posted_on() {
		$time_string = '<time class="entry-date published" datetime="%1$s">%2$s</time>';
		$time_string = sprintf(
			$time_string,
			esc_attr( get_the_date( DATE_W3C ) ),
			esc_html( get_the_date() )
		);
		echo $time_string; // phpcs:ignore WordPress.Security.EscapeOutput.OutputNotEscaped -- built from esc_* calls above.
	}
}

if ( ! function_exists( 'ot_posted_by' ) ) {
	function ot_posted_by() {
		printf(
			/* translators: %s: author display name */
			esc_html__( 'by %s', 'odditytrend' ),
			'<span class="author vcard">' . esc_html( get_the_author() ) . '</span>'
		);
	}
}

if ( ! function_exists( 'ot_pagination' ) ) {
	function ot_pagination() {
		the_posts_pagination( array(
			'mid_size'  => 1,
			'prev_text' => __( '&larr; Older', 'odditytrend' ),
			'next_text' => __( 'Newer &rarr;', 'odditytrend' ),
			'class'     => 'pagination',
		) );
	}
}
