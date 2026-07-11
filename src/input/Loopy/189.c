// Source: data/benchmarks/accelerating_invariant_generation/invgen/NetBSD_g_Ctoc.c
int __BLAST_NONDET;
/*@
  requires BASE_SZ > 0;
*/
void loopy_189(int BASE_SZ)
{
  
  int i;
  int j;
  int len = BASE_SZ;

  

  {;
//@ assert( 0 <= BASE_SZ-1 );
}

   
  
  i = 0;
  j = 0;
  while (1) {
    if ( len == 0 ){ 
      goto END;
    } else {
      {;
//@ assert( 0<= j );
}
 {;
//@ assert(j < BASE_SZ);
}

      {;
//@ assert( 0<= i );
}
 {;
//@ assert(i < BASE_SZ );
}

      if ( __BLAST_NONDET ) {
        i++;
        j++;
        goto END;
      }
    }
    i ++;
    j ++;
    len --;
  }

 END:  return;
}
