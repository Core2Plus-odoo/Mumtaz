<?php
/**
 * Single article template.
 */
if ( ! defined( 'ABSPATH' ) ) {
	exit;
}
get_header();
?>
<div class="content-layout">
	<div>
		<?php
		while ( have_posts() ) :
			the_post();
			get_template_part( 'template-parts/content', 'single' );

			if ( comments_open() || get_comments_number() ) :
				echo '<div class="comments-area">';
				comments_template();
				echo '</div>';
			endif;
		endwhile;
		?>
	</div>
	<?php get_sidebar(); ?>
</div>
<?php get_footer(); ?>
