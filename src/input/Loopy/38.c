// Source: data/benchmarks/LinearArbitrary-SeaHorn/invgen/sendmail-mime7to8_arr_three_chars_no_test_ok.c
extern int unknown(void);

extern int unknown();

/*@
  requires fbuflen >0;
*/
void loopy_38(int fbuflen)
{
  
  
  int fb;
  
  
  fb = 0;
  while (unknown())
  {
    
    if (unknown())
      break;

    if (unknown())
      break;

    {;
//@ assert(0<=fb);
}

    {;
//@ assert(fb<fbuflen);
}

    fb++;
    if (fb >= fbuflen-1)
      fb = 0;

    {;
//@ assert(0<=fb);
}

    {;
//@ assert(fb<fbuflen);
}

    fb++;
    if (fb >= fbuflen-1)
      fb = 0;

    {;
//@ assert(0<=fb);
}

    {;
//@ assert(fb<fbuflen);
}

    fb++;
    if (fb >= fbuflen-1)
      fb = 0;
  }

  if (fb > 0)
  {
    
    {;
//@ assert(0<=fb);
}

    {;
//@ assert(fb<fbuflen);
}

  }

 END:  return;
}